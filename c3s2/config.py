"""
Configuration de C3S² : chemins, clé API CDS, réglages pédagogiques.

Contrairement à la version Streamlit, cette application ne lit aucun secret
depuis `st.secrets` : elle s'appuie uniquement sur l'environnement, ce qui la
rend compatible avec Vercel (Environment Variables), un `.env` local et le
fichier officiel `%USERPROFILE%\\.cdsapirc`.

Règle absolue : la clé n'est jamais renvoyée au client. L'API n'expose qu'une
forme masquée (`a4b4…d32f`) et la source qui l'a fournie.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Racine du projet (dossier contenant `vercel.json`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Version de l'application, affichée dans l'en-tête et le diagnostic.
APP_VERSION = "2.0.0"
APP_NAME = "C3S² Climate Lab"

# --------------------------------------------------------------------------- #
# Dossiers
# --------------------------------------------------------------------------- #


def _writable_dir(candidates: list[Path]) -> tuple[Path, bool]:
    """
    Choisit le premier dossier réellement inscriptible parmi `candidates`.

    Sur Vercel, le système de fichiers de la fonction est en lecture seule à
    l'exception de `/tmp` : sans cette précaution, le cache CDS planterait au
    premier téléchargement.
    """
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate, candidate == candidates[0]
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "c3s2"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, False


DATA_DIR, DATA_DIR_IS_DEFAULT = _writable_dir(
    [
        Path(os.environ["C3S2_DATA_DIR"]) if os.environ.get("C3S2_DATA_DIR") else PROJECT_ROOT / "data",
        Path(tempfile.gettempdir()) / "c3s2",
    ]
)

#: Vrai quand on tourne sur un système de fichiers en lecture seule (Vercel).
IS_READONLY_DEPLOYMENT = not DATA_DIR_IS_DEFAULT

CACHE_DIR = DATA_DIR / "cache"
MAPS_DIR = DATA_DIR / "maps"
PRECOMPUTED_DIR = DATA_DIR / "precomputed"
#: Dossier des fonds de carte GeoJSON (déployé avec le code, lecture seule).
STATIC_MAPS_DIR = PROJECT_ROOT / "data" / "maps"
#: Copie des cartes statiques JSON livrée avec le code : le dossier `public/`
#: étant servi par le CDN, il n'est pas visible des fonctions (Vercel).
BUNDLED_MAPS_DIR = PROJECT_ROOT / "data" / "static_maps"

for _d in (CACHE_DIR, MAPS_DIR, PRECOMPUTED_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def is_vercel() -> bool:
    """Vrai quand l'application tourne sur Vercel."""
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def is_local() -> bool:
    return not is_vercel()


# --------------------------------------------------------------------------- #
# Réglages climatiques
# --------------------------------------------------------------------------- #

#: Normale climatique de référence (OMM).
REFERENCE_PERIOD = (1991, 2020)

#: Dernière année complète disponible dans les séries préparées.
LAST_COMPLETE_YEAR = 2024

#: Première année des séries préparées.
FIRST_YEAR = 1940

CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_CATALOGUE_URL = "https://cds.climate.copernicus.eu/api/catalogue/v1/collections"

ERA5_CITATION = (
    "Hersbach, H., Bell, B., Berrisford, P., et al. (2020). The ERA5 global "
    "reanalysis. Quarterly Journal of the Royal Meteorological Society, "
    "146(730), 1999-2049. https://doi.org/10.1002/qj.3803"
)
ERA5_ATTRIBUTION = (
    "Generated using Copernicus Climate Change Service information 2024 "
    "(C3S/CAMS), with the appropriate credit."
)
ERA5_LICENCE = "CC BY 4.0"

# --------------------------------------------------------------------------- #
# Code enseignant
# --------------------------------------------------------------------------- #


def teacher_code() -> str:
    """
    Code déverrouillant les corrigés.

    Réglable via `C3S2_TEACHER_CODE` ; la valeur par défaut reste valable pour
    une salle équipée qui n'a pas touché à la configuration.
    """
    return os.environ.get("C3S2_TEACHER_CODE") or os.environ.get("C3S_TEACHER_CODE") or "2027"


def check_teacher_code(candidate: str | None) -> bool:
    """Compare en ignorant la casse et les espaces de bord."""
    if not candidate:
        return False
    return candidate.strip().lower() == teacher_code().strip().lower()


# --------------------------------------------------------------------------- #
# Clé CDS
# --------------------------------------------------------------------------- #


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Lit un `.env` minimal (`CLE=valeur`), sans dépendance externe."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _parse_cdsapirc(path: Path) -> dict[str, str]:
    """Lit un `.cdsapirc` (petit YAML : `url:` puis `key:`)."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip().lower()] = value.strip().strip("'\"")
    return out


def user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def cdsapirc_path() -> Path:
    return user_home() / ".cdsapirc"


@dataclass
class CDSConfig:
    """Configuration CDS effectivement retenue (jamais exposée en clair)."""

    url: str | None = None
    key: str | None = None
    source: str = "introuvable"
    path: Path | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    def masked_key(self) -> str:
        """Clé tronquée, sûre à afficher devant une classe."""
        if not self.key:
            return "—"
        if ":" in self.key:
            head, _, tail = self.key.partition(":")
            return f"{head[:4]}…:{tail[-4:]}"
        if len(self.key) >= 14:
            return f"{self.key[:4]}…{self.key[-4:]}"
        return "••••"

    def as_dict(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured,
            "source": self.source,
            "url": self.url,
            "masked_key": self.masked_key(),
        }


def resolve_cds_config() -> CDSConfig:
    """
    Recherche la configuration CDS, par ordre de priorité :

    1. variables d'environnement `CDSAPI_URL` / `CDSAPI_KEY`
       (c'est la voie Vercel : *Project Settings → Environment Variables*) ;
    2. fichier `.cdsapirc` du dossier personnel (méthode officielle ECMWF) ;
    3. fichier `.env` à la racine du projet (développement local) ;
    4. fichier `.cdsapirc` local au projet (salle de PC).
    """
    env_url = os.environ.get("CDSAPI_URL", "").strip()
    env_key = os.environ.get("CDSAPI_KEY", "").strip()
    if env_url and env_key:
        return CDSConfig(
            url=env_url.rstrip("/"),
            key=env_key,
            source="environnement (CDSAPI_URL / CDSAPI_KEY)",
        )

    official = cdsapirc_path()
    conf = _parse_cdsapirc(official)
    if conf.get("url") and conf.get("key"):
        return CDSConfig(
            url=conf["url"].rstrip("/"),
            key=conf["key"],
            source=f"fichier {official}",
            path=official,
        )

    dotenv = _parse_dotenv(PROJECT_ROOT / ".env")
    if dotenv.get("CDSAPI_URL") and dotenv.get("CDSAPI_KEY"):
        return CDSConfig(
            url=dotenv["CDSAPI_URL"].rstrip("/"),
            key=dotenv["CDSAPI_KEY"],
            source="fichier .env du projet",
            path=PROJECT_ROOT / ".env",
        )

    local = PROJECT_ROOT / ".cdsapirc"
    conf = _parse_cdsapirc(local)
    if conf.get("url") and conf.get("key"):
        return CDSConfig(
            url=conf["url"].rstrip("/"),
            key=conf["key"],
            source=f"fichier {local}",
            path=local,
        )

    return CDSConfig()


# --------------------------------------------------------------------------- #
# Diagnostic
# --------------------------------------------------------------------------- #


def app_info() -> dict[str, Any]:
    """Résumé de l'environnement, renvoyé par `/api/config`."""
    import platform

    versions: dict[str, str] = {}
    for name in ("cdsapi", "xarray", "numpy", "pandas", "fastapi", "h5netcdf", "netCDF4"):
        try:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", "installé")
        except Exception:  # noqa: BLE001
            versions[name] = "absent"

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "host": "vercel" if is_vercel() else "local",
        "read_only_fs": IS_READONLY_DEPLOYMENT,
        "data_dir": str(DATA_DIR),
        "versions": versions,
        "reference_period": f"{REFERENCE_PERIOD[0]}-{REFERENCE_PERIOD[1]}",
    }
