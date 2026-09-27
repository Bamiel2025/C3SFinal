"""
Préparation des cartes climatiques statiques.

    python scripts/prepare_maps.py               # toutes les cartes
    python scripts/prepare_maps.py t2m_janvier   # une seule
    python scripts/prepare_maps.py --force

Chaque carte est téléchargée une fois (moyenne ERA5 1991-2020 sur l'Europe),
réduite à un demi-degré, puis écrite dans `public/assets/maps/`. Le navigateur
la récupère ensuite depuis le CDN : aucune fonction Vercel, aucun délai, aucune
consommation de quota CDS pendant la séance.

Le script est idempotent : sans `--force`, les cartes déjà présentes sont
laissées intactes.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c3s2 import config, fields, places  # noqa: E402

#: Domaine des cartes pédagogiques : l'Europe.
EUROPE = (72.0, -25.0, 33.0, 45.0)

#: (identifiant, variable, mois, titre court)
SCALAR_MAPS = [
    ("t2m_janvier", "2m_temperature", 1, "Température en janvier"),
    ("t2m_juillet", "2m_temperature", 7, "Température en juillet"),
    ("tp_janvier", "total_precipitation", 1, "Précipitations en janvier"),
    ("tp_juillet", "total_precipitation", 7, "Précipitations en juillet"),
    ("mslp_janvier", "mean_sea_level_pressure", 1, "Pression en janvier"),
]

WIND_MAPS = [
    ("vent_janvier", 1, "Vent en janvier"),
]

ALL_IDS = [m[0] for m in SCALAR_MAPS] + [m[0] for m in WIND_MAPS]


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def build_one(map_id: str, force: bool) -> bool:
    target = fields.PUBLIC_MAPS_DIR / f"{map_id}.json"
    if target.is_file() and not force:
        log(f"{map_id}: déjà présente ({target.stat().st_size / 1e3:.0f} ko), ignorée.")
        return False

    t0 = time.perf_counter()
    scalar = next((m for m in SCALAR_MAPS if m[0] == map_id), None)
    wind = next((m for m in WIND_MAPS if m[0] == map_id), None)

    if scalar is not None:
        _, variable, month, _title = scalar
        payload = fields.field_from_cds(
            variable, area=EUROPE, month=month, years=config.REFERENCE_PERIOD
        )
    elif wind is not None:
        _, month, _title = wind
        payload = fields.wind_map_from_cds(EUROPE, month=month, years=config.REFERENCE_PERIOD)
    else:
        raise KeyError(f"Carte inconnue : {map_id!r}. Disponibles : {ALL_IDS}")

    path = fields.save_static_map(map_id, payload)
    log(
        f"{map_id}: {len(payload['lat'])}×{len(payload['lon'])} cellules, "
        f"{path.stat().st_size / 1e3:.0f} ko, {time.perf_counter() - t0:.1f} s"
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Préparation des cartes C3S²")
    parser.add_argument("ids", nargs="*", help="identifiants (défaut : toutes)")
    parser.add_argument("--force", action="store_true", help="re-télécharge les cartes")
    args = parser.parse_args(argv)

    ids = args.ids or ALL_IDS
    unknown = [i for i in ids if i not in ALL_IDS]
    if unknown:
        parser.error(f"identifiants inconnus : {unknown} — attendus : {ALL_IDS}")

    cfg = config.resolve_cds_config()
    log(f"Clé CDS : {cfg.masked_key() or 'absente'} — domaine {places.area_label(EUROPE)}")

    done = 0
    for map_id in ids:
        try:
            done += int(build_one(map_id, args.force))
        except Exception as exc:  # noqa: BLE001 - une carte en échec n'arrête pas les autres
            log(f"{map_id}: ÉCHEC — {exc}")

    index = fields.list_maps()
    log(f"Terminé : {done} carte(s) écrite(s), inventaire = {len(index)} entrée(s).")
    return 0 if done or ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
