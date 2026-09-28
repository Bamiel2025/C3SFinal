"""
Vérifie deux choses sur les activités :

1. la structure attendue (4 étapes, corrigé, indice, minutes) ;
2. la cohérence **chiffrée** des corrigés avec les données pré-calculées —
   un corrigé qui contredit les CSV est pire qu'un corrigé absent.
"""

from __future__ import annotations

import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from c3s2 import activities, config, store

ALL = activities.ACTIVITIES
ALLOWED_CHARTS = {"none", "climato", "ombro", "annual", "anomalies", "compare", "map", "heat"}


def test_ten_activities_with_four_steps() -> None:
    assert len(ALL) == 10
    keys = [a.key for a in ALL]
    assert len(set(keys)) == len(keys)
    for act in ALL:
        assert len(act.steps) == 4, act.key
        assert act.title and act.introduction
        assert act.default_cities
        for step in act.steps:
            assert step.title and step.instruction
            assert step.hint
            assert step.expected and len(step.expected) > 40
            assert step.chart in ALLOWED_CHARTS
            assert 1 <= step.minutes <= 20


def test_list_activities_hides_answers_without_code() -> None:
    hidden = activities.list_activities(with_answers=False)
    shown = activities.list_activities(with_answers=True)
    assert len(hidden) == len(shown) == 10
    assert "expected" not in hidden[0]["steps"][0]
    assert "expected" in shown[0]["steps"][0]
    assert config.check_teacher_code("") is False
    assert config.check_teacher_code(config.teacher_code()) is True


# --------------------------------------------------------------------------- #
# Données : normale mensuelle 1991-2020, comme celle affichée aux élèves
# --------------------------------------------------------------------------- #


def _clim(df: pd.DataFrame, city: str) -> pd.Series:
    sub = df.loc["1991":"2020", city]
    return sub.groupby(sub.index.month).mean()


@pytest.fixture(scope="module")
def temp() -> pd.DataFrame:
    frame = store._frame("2m_temperature")
    assert frame is not None, "CSV de température manquant : lancez scripts/prepare_data.py"
    return frame


@pytest.fixture(scope="module")
def precip() -> pd.DataFrame:
    frame = store._frame("total_precipitation")
    assert frame is not None, "CSV de précipitations manquant : lancez scripts/prepare_data.py"
    return frame


def _expected(key: str) -> list[str]:
    act = next(a for a in ALL if a.key == key)
    return [s.expected for s in act.steps]


def test_amplitudes_quoted_in_corriges(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("ocean_continent"))
    for city in ("Brest", "Strasbourg", "Marseille"):
        m = _clim(temp, city)
        amplitude = m.max() - m.min()
        quoted = f"{amplitude:.1f}".replace(".", ",")
        assert quoted in answers, f"amplitude {city} ({quoted}) absente du corrigé"


def test_winter_values_quoted(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("ocean_continent"))
    for city in ("Brest", "Strasbourg"):
        m = _clim(temp, city)
        quoted = f"{m.min():.1f}".replace(".", ",")
        assert quoted in answers, f"mois le plus froid {city} ({quoted}) absent du corrigé"


def test_precipitation_totals_quoted(precip: pd.DataFrame) -> None:
    answers = " ".join(_expected("cycle_eau"))
    marseille = _clim(precip, "Marseille").sum()
    dakar = _clim(precip, "Dakar").sum()
    # Marseille reçoit plus d'eau que Dakar : l'ordre du corrigé doit le dire.
    assert marseille > dakar
    assert answers.index("Marseille") < answers.index("Dakar") or "Marseille : environ" in answers
    # Les totaux cités (600 mm / 280 mm) sont des arrondis des vraies valeurs.
    assert round(marseille, -2) == 600
    assert round(dakar, -2) == 300 or round(dakar, -1) == 280


def test_january_order_quoted(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("latitude"))
    values = {c: _clim(temp, c)[1] for c in ("Dakar", "Paris", "Reykjavik", "Longyearbyen")}
    assert values["Dakar"] > values["Paris"] > values["Reykjavik"] > values["Longyearbyen"]
    for city in ("Dakar", "Paris"):
        quoted = f"{values[city]:.1f}".replace(".", ",")
        assert quoted in answers, f"janvier {city} ({quoted}) absent du corrigé"
    # L'écart Dakar − Paris cité dans le corrigé.
    gap = f"{values['Dakar'] - values['Paris']:.0f} °C"
    assert gap in answers


def test_paris_trend_quoted(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("avant_apres"))
    annual = temp["Paris"].resample("YE").mean()
    annual.index = annual.index.year
    p1 = annual.loc[1941:1970].mean()
    p2 = annual.loc[1991:2020].mean()
    delta = p2 - p1
    assert delta > 0.5  # le réchauffement est réel dans les données
    assert f"{p1:.1f}".replace(".", ",") in answers
    assert f"{p2:.1f}".replace(".", ",") in answers


def test_mediterranean_precip_minimum(precip: pd.DataFrame) -> None:
    answers = " ".join(_expected("cycle_eau"))
    marseille = _clim(precip, "Marseille")
    assert marseille.idxmin() == 7  # juillet
    assert "juillet" in answers
    assert f"{marseille[7]:.0f} mm" in answers or "10 mm" in answers


def test_each_step_maps_to_a_renderable_chart() -> None:
    for act in ALL:
        for n, step in enumerate(act.steps, start=1):
            if step.chart == "none":
                assert act.key == "latitude" and n == 1
            if step.chart == "map":
                assert act.key in {"cartes_climatiques", "vent_pression", "pluies_europe"}


def test_minutes_sum_to_a_class_session() -> None:
    for act in ALL:
        total = sum(s.minutes for s in act.steps)
        assert 20 <= total <= 45, f"{act.key}: {total} min de questions seules"


def test_days_in_month_helper_parity() -> None:
    # Petit garde-fou : les cumuls mensuels de pluie en mm/mois dépendent du
    # nombre de jours du mois dans les conversions CDS.
    assert calendar.monthrange(2020, 2)[1] == 29
    assert calendar.monthrange(2021, 2)[1] == 28


def test_regimes_amplitudes_quoted(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("regimes_monde"))
    for city, quoted in (("Singapore", "1,7"), ("Paris", "15,3"), ("Longyearbyen", "19,7")):
        m = _clim(temp, city)
        assert f"{m.max() - m.min():.1f}".replace(".", ",") == quoted
        assert quoted in answers
    assert "−13,6" in answers  # signe moins typographique U+2212


def test_portrait_bordeaux_quoted(temp: pd.DataFrame, precip: pd.DataFrame) -> None:
    answers = " ".join(_expected("portrait_climat"))
    t = _clim(temp, "Bordeaux")
    p = _clim(precip, "Bordeaux")
    assert f"{t.min():.1f}".replace(".", ",") in answers  # 6,7 en janvier
    assert f"{t.max():.1f}".replace(".", ",") in answers  # 21,6 en juillet-août
    assert f"{t.max() - t.min():.1f}".replace(".", ",") in answers  # 15,0
    assert round(p.sum(), -1) == 820
    assert "820" in answers


def _map_point(map_id: str, lon: float, lat: float) -> float:
    root = Path(__file__).resolve().parent.parent
    g = json.loads(
        (root / "public" / "assets" / "maps" / f"{map_id}.json").read_text(encoding="utf-8")
    )
    lats = np.array(g["lat"])
    lons = np.array(g["lon"])
    z = np.array(g["z"], dtype=float)
    i = int(np.argmin(abs(lats - lat)))
    j = int(np.argmin(abs(lons - lon)))
    return round(float(z[i, j]))


def test_pluies_europe_map_values() -> None:
    answers = " ".join(_expected("pluies_europe"))
    assert 280 <= _map_point("tp_janvier", 6, 61) <= 300  # côte ouest norvégienne
    assert "293" in answers
    assert _map_point("tp_juillet", -4, 37) <= 8  # Andalousie
    assert "4 mm" in answers
    assert _map_point("tp_juillet", 7, 46) >= 140  # Alpes
    assert "153" in answers
