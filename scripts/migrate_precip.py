"""
Migration des précipitations : du débit moyen journalier au cumul mensuel.

Les moyennes mensuelles ERA5 livrent les précipitations en **mètres par jour**
(moyenne journalière du mois). Le fichier `villes_precipitations.csv` hérité de
la version 1 contenait donc des valeurs de l'ordre de 2 pour janvier, alors
qu'un cumul mensuel réel est de l'ordre de 60 mm : tous les diagrammes
ombrothermiques étaient faux d'un facteur ~30.

Ce script convertit le fichier une fois pour toutes en cumuls mensuels
(mm/mois), en multipliant chaque ligne par le nombre de jours de son mois.
Un fichier marqueur empêche toute double conversion.

    python scripts/migrate_precip.py
"""

from __future__ import annotations

import calendar
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from c3s2 import config  # noqa: E402

SOURCE = "villes_precipitations.csv"
MARKER = config.PRECOMPUTED_DIR / ".precip_monthly_total"


def main() -> int:
    path = config.PRECOMPUTED_DIR / SOURCE
    if not path.is_file():
        print(f"Absent : {path}")
        return 1

    if MARKER.is_file():
        print("Déjà converti (marqueur présent) : rien à faire.")
        return 0

    frame = pd.read_csv(path, sep=";", index_col=0, parse_dates=True, encoding="utf-8-sig")
    frame.index = pd.to_datetime(frame.index)
    days = pd.Series(
        [calendar.monthrange(d.year, d.month)[1] for d in frame.index],
        index=frame.index,
        dtype="float64",
    )
    converted = frame.mul(days, axis=0)
    converted.to_csv(
        path,
        sep=";",
        float_format="%.2f",
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
    )
    MARKER.write_text("cumuls mensuels (mm/mois)\n", encoding="utf-8")
    print(
        f"Converti : {path.name} — {converted.shape[0]} mois × {converted.shape[1]} villes, "
        f"valeur avant {float(frame.iloc[:, 0].abs().max()):.2f} / après "
        f"{float(converted.iloc[:, 0].abs().max()):.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
