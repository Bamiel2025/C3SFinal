"""
Préparation des données pré-calculées de C3S².

Trois tâches :

* `cities`  — complète les villes qui manquent dans les CSV mensuels ERA5
              (Paris, Marseille, Aubagne, Montréal…) ;
* `heat`    — séries journalières maximum / minimum pour l'activité canicule ;
* `all`     — les deux.

    python scripts/prepare_data.py cities
    python scripts/prepare_data.py heat --years 2000-2024
    python scripts/prepare_data.py all --force

Chaque requête ERA5 prend 20 à 90 secondes : la préparation complète dure
quelques minutes et n'est à refaire que lorsque l'on ajoute des villes.
Les fichiers produits sont ensuite versionnés, donc l'application ne dépend
d'aucune clé à l'exécution.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from c3s2 import config, heat, places, series, store  # noqa: E402

#: Colonnes héritées de la v1 renommées pour correspondre à `places`.
COLUMN_ALIASES = {
    "Moscow": "Moscou",
}

#: Villes retenues pour les données journalières de l'activité canicule.
DEFAULT_HEAT_CITIES = ["Marseille", "Paris", "Lyon", "Bordeaux"]

FIRST_YEAR = config.FIRST_YEAR
LAST_YEAR = config.LAST_COMPLETE_YEAR


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def normalize_columns() -> None:
    """Aligne les noms de colonnes des CSV sur les noms de `places`."""
    for variable in store.PRECOMPUTED_FILES:
        frame = store._raw_frame(variable)
        if frame is None:
            continue
        renamed = {old: COLUMN_ALIASES[old] for old in COLUMN_ALIASES if old in frame.columns}
        if not renamed:
            continue
        frame = frame.rename(columns=renamed)
        store.replace_frame(variable, frame)
        log(f"{variable}: colonnes renommées {renamed}")


def prepare_cities(force: bool = False) -> int:
    """Télécharge les villes absentes des CSV mensuels."""
    done = 0
    for variable in store.PRECOMPUTED_FILES:
        available = set(store.available_cities(variable))
        missing = [p for p in places.all_places() if p.name not in available]
        if force:
            missing = list(missing) + [
                p for p in places.all_places() if p.name in available
            ]
        if not missing:
            log(f"{variable}: toutes les villes présentes.")
            continue
        log(f"{variable}: {len(missing)} ville(s) à télécharger -> {', '.join(p.name for p in missing)}")

        for place in missing:
            t0 = time.perf_counter()
            try:
                result = series.fetch_cds(place, variable, FIRST_YEAR, LAST_YEAR)
            except Exception as exc:  # noqa: BLE001 - une ville en échec n'arrête pas les autres
                log(f"  ÉCHEC {place.name}: {exc}")
                continue
            column = pd.DataFrame({place.name: result.series})
            path = store.save_frame(variable, column)
            log(
                f"  OK {place.name} ({variable}) — {len(result.series)} mois, "
                f"{time.perf_counter() - t0:.1f} s -> {path.name}"
            )
            done += 1
    return done


def prepare_heat(
    force: bool = False,
    years: tuple[int, int] = (2000, 2024),
    cities: list[str] | None = None,
) -> int:
    """Télécharge les séries journalières (maximum / minimum) de l'activité."""
    start, end = years
    done = 0
    for city in cities or DEFAULT_HEAT_CITIES:
        for kind, filename in (("tmax", heat.TMAX_FILE), ("tmin", heat.TMIN_FILE)):
            frame = heat._load(filename)
            if not force and frame is not None and city in frame.columns:
                column = frame[city].dropna()
                if not column.empty and column.index[0].year <= start and column.index[-1].year >= end:
                    log(f"{filename}: {city} déjà couverte.")
                    continue

            place = places.get(city)
            if place is None:
                log(f"Ville inconnue : {city}")
                continue

            t0 = time.perf_counter()
            try:
                values = heat._fetch_daily(place, kind, start, end)
            except Exception as exc:  # noqa: BLE001
                log(f"  ÉCHEC {city}/{kind}: {exc}")
                continue
            path = store.save_daily(filename, pd.DataFrame({city: values}))
            log(
                f"  OK {city}/{kind} — {len(values)} jours, "
                f"{time.perf_counter() - t0:.1f} s -> {path.name}"
            )
            done += 1
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Préparation des données C3S²")
    parser.add_argument(
        "task", nargs="?", default="all", choices=["all", "cities", "heat"],
        help="quoi préparer (défaut : tout)",
    )
    parser.add_argument("--force", action="store_true", help="re-télécharge même ce qui existe")
    parser.add_argument("--years", default="2000-2024", help="période journalière (AAAA-AAAA)")
    parser.add_argument(
        "--cities",
        default="",
        help="liste de villes pour `heat`, séparées par des virgules (défaut : %s)"
        % ",".join(DEFAULT_HEAT_CITIES),
    )
    args = parser.parse_args(argv)

    first, last = (int(x) for x in args.years.split("-"))
    wanted = [c.strip() for c in args.cities.split(",") if c.strip()]
    cfg = config.resolve_cds_config()
    log(f"Clé CDS : {cfg.masked_key() or 'absente'} — période journalière {first}-{last}")

    normalize_columns()

    count = 0
    if args.task in ("cities", "all"):
        count += prepare_cities(force=args.force)
    if args.task in ("heat", "all"):
        count += prepare_heat(force=args.force, years=(first, last), cities=wanted or None)

    store.clear_cache()
    heat.clear_cache()
    log(f"Terminé : {count} téléchargement(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
