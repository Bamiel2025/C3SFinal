"""
Client du Climate Data Store : connexion, téléchargement, cache, lecture.

Le téléchargement est effectué par `cdsapi` (bibliothèque officielle ECMWF).
Deux particularités de ce projet :

* le cache vit dans un dossier **inscriptible** (`/tmp` sur Vercel) ;
* le fichier NetCDF est lu avec le premier moteur disponible
  (`netcdf4`, puis `h5netcdf`, puis `scipy`), ce qui évite qu'un déploiement
  ne dépende d'une seule bibliothèque binaire.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import config, datasets

ProgressFn = Callable[[float, str], None]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class CDSError(RuntimeError):
    """Erreur fonctionnelle du CDS (clé invalide, licence, quota…)."""


class CDSConfigError(CDSError):
    """Clé ou URL absente / invalide."""


class CDSDownloadError(CDSError):
    """Le téléchargement a échoué après plusieurs tentatives."""


# --------------------------------------------------------------------------- #
# Clé
# --------------------------------------------------------------------------- #

#: Valeurs saisies par oubli : ce sont des exemples de documentation.
PLACEHOLDERS = (
    "votre", "remplacez", "remplacer", "your", "changeme", "xxxx", "todo",
    "token", "cle", "key", "<", ">",
)


@dataclass
class KeyDiagnosis:
    """Verdict sur la clé saisie, avec une explication utilisable."""

    ok: bool
    label: str
    message: str
    hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "label": self.label,
            "message": self.message,
            "hint": self.hint,
        }


def diagnose_key(key: str | None) -> KeyDiagnosis:
    """
    Analyse une clé avant connexion.

    Le CDS attend un **jeton d'accès personnel** (*Personal Access Token*),
    ni le couple `identifiant:secret` abandonné en 2024, ni le *Client ID* /
    *Client secret* de l'API Web ECMWF. Ces trois formats se ressemblent et se
    confondent : les distinguer ici évite une erreur d'authentification
    difficile à interpréter.
    """
    value = (key or "").strip()

    if not value:
        return KeyDiagnosis(
            False, "clé absente", "Aucun jeton n'a été détecté.",
            "Ajoutez CDSAPI_KEY dans les variables d'environnement du projet "
            "(Vercel : Settings → Environment Variables), ou créez un fichier "
            ".cdsapirc local.",
        )

    lowered = value.lower()
    if any(marker in lowered for marker in PLACEHOLDERS) and len(value) < 60:
        return KeyDiagnosis(
            False, "valeur d'exemple",
            "Cette valeur ressemble à un exemple de documentation, pas à un jeton réel.",
            "Collez le jeton de la section « Set up the CDS API personal access token » "
            "de https://cds.climate.copernicus.eu/user",
        )

    if ":" in value:
        return KeyDiagnosis(
            False, "ancien format identifiant:secret",
            "Le CDS n'accepte plus le format `identifiant:secret` depuis 2024.",
            "Récupérez un jeton personnel sur https://cds.climate.copernicus.eu/user "
            "(section « Set up the CDS API personal access token »).",
        )

    if len(value) < 20:
        return KeyDiagnosis(
            False, "clé trop courte",
            f"La valeur ne fait que {len(value)} caractères : c'est trop court pour un jeton CDS.",
            "Le jeton du CDS est une longue chaîne du type a1b2c3d4-…. Le « Client ID » "
            "et le « Client secret » de votre profil ECMWF sont refusés ici.",
        )

    return KeyDiagnosis(
        True, "jeton d'accès personnel",
        "La valeur a la forme attendue d'un jeton d'accès personnel du CDS.",
        "Si le téléchargement échoue encore, ouvrez la page du jeu de données sur le "
        "portail CDS et acceptez ses conditions d'utilisation.",
    )


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


def build_client(cfg: config.CDSConfig):
    """Instancie un client `cdsapi` à partir de la configuration."""
    if not cfg.is_configured:
        raise CDSConfigError("Clé API absente : voir la page CDS.")
    diagnosis = diagnose_key(cfg.key)
    if not diagnosis.ok:
        raise CDSConfigError(f"{diagnosis.message} {diagnosis.hint}")
    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover
        raise CDSConfigError("La bibliothèque `cdsapi` n'est pas installée.") from exc
    return cdsapi.Client(url=cfg.url, key=cfg.key, quiet=True)


def cache_key(dataset: str, request: dict[str, Any]) -> str:
    """Empreinte stable d'une requête, servant de nom de fichier de cache."""
    payload = json.dumps({"dataset": dataset, "request": request}, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def retrieve(
    cfg: config.CDSConfig,
    dataset: str,
    request: dict[str, Any],
    *,
    use_cache: bool = True,
    max_retries: int = 2,
    progress: ProgressFn | None = None,
) -> Path:
    """
    Télécharge une requête CDS et renvoie le chemin du fichier obtenu.

    Le fichier est mis en cache : un second appel identique est instantané,
    ce qui compte beaucoup en classe. Les archives ZIP renvoyées par le CDS
    sont automatiquement extraites.
    """
    stamp = cache_key(dataset, request)
    target = config.CACHE_DIR / f"{stamp}.nc"

    if use_cache and target.exists() and target.stat().st_size > 0:
        if progress:
            progress(1.0, "Données déjà téléchargées (cache local).")
        return target

    client = build_client(cfg)
    tmp = target.with_suffix(".part")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if progress:
                progress(0.05, f"Requête envoyée au CDS (essai {attempt}/{max_retries})…")
            client.retrieve(dataset, request, str(tmp))
            break
        except Exception as exc:  # noqa: BLE001 - le CDS lève des exceptions variées
            last_error = exc
            message = str(exc)
            # Inutile de réessayer une clé refusée ou un quota dépassé.
            if any(marker in message.lower() for marker in ("401", "403", "licen", "quota", "cost limit")):
                raise CDSDownloadError(_explain(message)) from exc
            if progress:
                progress(0.05, f"Échec : {message[:120]}. Nouvelle tentative…")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    else:
        raise CDSDownloadError(_explain(str(last_error)))

    resolved = _normalise_output(tmp, target)
    if progress:
        progress(1.0, f"Téléchargement terminé ({resolved.stat().st_size / 1e6:.1f} Mo).")
    return resolved


def _explain(message: str) -> str:
    """Traduit les erreurs fréquentes du CDS en français utilisable."""
    lowered = message.lower()
    if "401" in lowered or "unauthor" in lowered or "token" in lowered:
        return (
            "Jeton refusé par le CDS (401). Vérifiez qu'il s'agit bien du jeton "
            "d'accès personnel du profil CDS, et non d'un Client ID / Client secret."
        )
    if "licen" in lowered or "403" in lowered:
        return (
            "Conditions d'utilisation non acceptées (403). Ouvrez la page du jeu de "
            "données sur cds.climate.copernicus.eu et cliquez sur « Accept » en bas "
            "du formulaire."
        )
    if "cost limit" in lowered or "quota" in lowered:
        return (
            "Quota du CDS dépassé pour cette requête : réduisez la période ou "
            "l'étendue géographique, puis réessayez plus tard."
        )
    if "timeout" in lowered or "timed out" in lowered:
        return "Le CDS n'a pas répondu à temps. Réessayez dans quelques minutes."
    return message[:400]


def _normalise_output(tmp: Path, target: Path) -> Path:
    """Normalise la sortie du CDS vers un fichier NetCDF unique."""
    if not tmp.exists():
        raise CDSDownloadError("Le CDS n'a renvoyé aucun fichier.")

    if zipfile.is_zipfile(tmp):
        with zipfile.ZipFile(tmp) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith((".nc", ".nc4", ".grib"))]
            if not members:
                raise CDSDownloadError("L'archive renvoyée par le CDS ne contient pas de fichier NetCDF.")
            with zf.open(members[0]) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp.unlink(missing_ok=True)
        return target

    tmp.replace(target)
    return target


# --------------------------------------------------------------------------- #
# Lecture NetCDF
# --------------------------------------------------------------------------- #


def open_dataset(path: Path):
    """
    Ouvre un fichier NetCDF avec le premier moteur disponible.

    `netcdf4` gère les deux formats (classic et HDF5) ; `h5netcdf` couvre les
    déploiements où `netCDF4` n'est pas installable ; `scipy` lit les anciens
    fichiers classic.
    """
    import xarray as xr

    errors: list[str] = []
    for engine in ("netcdf4", "h5netcdf", "scipy"):
        try:
            ds = xr.open_dataset(path, engine=engine)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{engine}: {type(exc).__name__}")
            continue
        for dim in ("time", "valid_time"):
            if dim in ds.coords:
                try:
                    ds[dim] = ds[dim].astype("datetime64[ns]")
                except (TypeError, ValueError):  # pragma: no cover
                    pass
        if "valid_time" in ds.dims and "time" not in ds.dims:
            ds = ds.rename({"valid_time": "time"})
        return ds

    raise CDSError(f"Lecture impossible du fichier NetCDF ({', '.join(errors)}).")


def find_variable(ds, variable: str):
    """Retrouve le champ demandé dans le fichier (nom long ou code court)."""
    available = list(ds.data_vars)
    found = None
    for name in datasets.name_candidates(variable):
        if name in ds:
            found = ds[name]
            break

    if found is None:
        stem = datasets.SHORT_NAMES.get(variable, variable)
        for name in available:
            if name == variable or name == stem or stem in name:
                found = ds[name]
                break

    if found is None:
        raise CDSError(
            f"Variable « {variable} » absente du fichier (code court attendu : "
            f"« {datasets.SHORT_NAMES.get(variable, '?')} »). "
            f"Variables disponibles : {available}"
        )

    for dim in ("number", "expver", "depth", "level", "depthBelowLand"):
        if dim in found.dims and found.sizes.get(dim) == 1:
            found = found.squeeze(dim, drop=True)
    if "latitude" not in found.coords and "lat" in found.coords:
        found = found.rename({"lat": "latitude", "lon": "longitude"})
    return found


def to_display_units(da, variable: str) -> tuple[Any, str]:
    """
    Convertit une variable dans son unité d'affichage.

    On se fie d'abord à l'unité inscrite par le CDS dans le fichier, puis à la
    table de correspondance. Attention : cette conversion ne produit **que**
    l'unité du fichier (mm/jour pour les précipitations mensuelles) ; le cumul
    mensuel se fait ensuite, mois par mois, dans `series.py`.
    """
    unit = str(da.attrs.get("units", "")).strip()
    if unit in datasets.FILE_UNITS:
        factor, target, offset = datasets.FILE_UNITS[unit]
        return da * factor + offset, target
    variable_meta = datasets.VARIABLES.get(variable)
    if variable_meta and variable_meta.kind == "temperature":
        return da - datasets.KELVIN_OFFSET, "°C"
    return da, unit or (variable_meta.unit if variable_meta else "")


# --------------------------------------------------------------------------- #
# Diagnostic de connexion
# --------------------------------------------------------------------------- #


@dataclass
class ConnectionReport:
    """Résultat du diagnostic, affiché dans la page CDS."""

    ok: bool
    title: str
    detail: str
    hint: str = ""
    latency_s: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "title": self.title,
            "detail": self.detail,
            "hint": self.hint,
            "latency_s": round(self.latency_s, 2) if self.latency_s else None,
        }


def test_connection(cfg: config.CDSConfig, *, deep: bool = False) -> ConnectionReport:
    """
    Vérifie la configuration CDS.

    - `deep=False` : présence de la clé et joignabilité du portail (aucun quota) ;
    - `deep=True`  : une vraie petite requête, pour valider l'authentification
      **et** l'acceptation des conditions d'utilisation.
    """
    if not cfg.is_configured:
        diagnosis = diagnose_key(cfg.key)
        return ConnectionReport(
            ok=False,
            title="Aucune clé API détectée",
            detail="L'application n'a trouvé ni variable CDSAPI_KEY, ni fichier .cdsapirc.",
            hint=diagnosis.hint,
        )

    diagnosis = diagnose_key(cfg.key)
    if not diagnosis.ok:
        return ConnectionReport(False, "Clé invalide", diagnosis.message, diagnosis.hint)

    t0 = time.perf_counter()
    try:
        import requests
    except ImportError:  # pragma: no cover
        return ConnectionReport(False, "Client HTTP absent", "Installer `requests`.")

    try:
        r = requests.get(config.CDS_CATALOGUE_URL, params={"limit": 1}, timeout=20)
        if r.status_code >= 500:
            return ConnectionReport(False, "Portail CDS en erreur", f"Statut HTTP {r.status_code}.")
    except Exception as exc:  # noqa: BLE001 - réseau
        return ConnectionReport(
            False, "Portail CDS injoignable", f"{type(exc).__name__} : {exc}",
            hint="Vérifiez la connexion Internet et les réglages de proxy.",
        )

    if not deep:
        return ConnectionReport(
            True,
            "Configuration valide",
            f"Clé reconnue par l'application (source : {cfg.source}). Le portail CDS répond ; "
            "le test d'authentification n'a pas été lancé.",
            latency_s=time.perf_counter() - t0,
        )

    try:
        client = build_client(cfg)
        target = config.CACHE_DIR / "_connection_test.nc"
        client.retrieve(
            "reanalysis-era5-single-levels-monthly-means",
            {
                "product_type": "monthly_averaged_reanalysis",
                "variable": ["2m_temperature"],
                "year": ["2023"],
                "month": ["01"],
                "time": "00:00",
                "area": [46.0, 2.0, 45.0, 3.0],
                "data_format": "netcdf",
                "download_format": "unarchived",
            },
            str(target),
        )
        target.unlink(missing_ok=True)
        return ConnectionReport(
            True,
            "Connexion CDS opérationnelle",
            "Le CDS a accepté la requête et renvoyé des données pour un point test en France. "
            "Toutes les licences utilisées sont acceptées.",
            latency_s=time.perf_counter() - t0,
        )
    except Exception as exc:  # noqa: BLE001 - dépend du compte
        detail = f"{type(exc).__name__} : {exc}"
        lowered = detail.lower()
        if "licen" in lowered or "403" in lowered:
            return ConnectionReport(
                True,
                "Clé acceptée — conditions d'utilisation à accepter",
                "Le CDS a reconnu votre jeton. Le téléchargement n'est bloqué que parce que les "
                "conditions d'utilisation du jeu de données ne sont pas encore acceptées : "
                "ouvrez sa page sur le portail CDS et cliquez sur « Accept ».",
                latency_s=time.perf_counter() - t0,
            )
        return ConnectionReport(
            False, "Échec du test approfondi", detail,
            hint=_explain(detail),
            latency_s=time.perf_counter() - t0,
        )


# --------------------------------------------------------------------------- #
# Utilitaires de lecture
# --------------------------------------------------------------------------- #


def nearest_index(coord: np.ndarray, value: float) -> int:
    return int(np.abs(np.asarray(coord) - value).argmin())


def point_series(da, lat: float, lon: float) -> pd.Series:
    """Série temporelle au point de grille le plus proche."""
    lat_c = da["latitude"].values
    lon_c = da["longitude"].values
    sub = da.isel(
        latitude=nearest_index(lat_c, lat),
        longitude=nearest_index(lon_c, lon),
    )
    return pd.Series(np.asarray(sub.values).astype("float64"), index=pd.to_datetime(da["time"].values))


def box_mean_series(da, lat: float, lon: float, half: float = 0.25) -> pd.Series:
    """Moyenne sur une petite boîte autour du point (lisse le bruit de maille)."""
    lat_c = da["latitude"].values
    lon_c = da["longitude"].values
    lat_slice = slice(
        max(float(lat_c.min()), lat - half),
        min(float(lat_c.max()), lat + half),
    )
    lon_slice = slice(
        max(float(lon_c.min()), lon - half),
        min(float(lon_c.max()), lon + half),
    )
    sub = da.sel(latitude=lat_slice, longitude=lon_slice)
    if sub.sizes.get("latitude", 0) == 0 or sub.sizes.get("longitude", 0) == 0:
        return point_series(da, lat, lon)
    return sub.mean(dim=["latitude", "longitude"]).to_series()


def field2d(da, *, month: int | None = None, season: str | None = None):
    """Champ 2D prêt à cartographier (moyenne sur la période ou le mois)."""
    if month is not None and "time" in da.dims:
        da = da.sel(time=da.time.dt.month == month)
    elif season:
        groups = {"djf": [12, 1, 2], "mam": [3, 4, 5], "jja": [6, 7, 8], "son": [9, 10, 11]}
        months = groups.get(season.lower(), groups["djf"])
        da = da.sel(time=da.time.dt.month.isin(months))
    if "time" in da.dims:
        da = da.mean(dim="time")
    return da
