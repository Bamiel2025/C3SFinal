"""
Vérifie deux choses sur les activités :

1. la structure attendue (4 étapes, corrigé, indice, minutes) ;
2. la cohérence **chiffrée** des corrigés avec les données pré-calculées —
   un corrigé qui contredit les CSV est pire qu'un corrigé absent.
"""

from __future__ import annotations

import calendar

import pandas as pd
import pytest

from c3s2 import activities, config, store

ALL = activities.ACTIVITIES
ALLOWED_CHARTS = {"none", "climato", "ombro", "annual", "anomalies", "compare", "map", "heat"}


def test_eight_activities_with_four_steps() -> None:
    assert len(ALL) == 8
    keys = [a.key for a in ALL]
    assert len(set(keys)) == len(keys)
    for act in ALL:
        assert len(act.steps) == 4, act.key
        assert act.title and act.introduction and act.teacher_tip
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
    assert len(hidden) == len(shown) == 8
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
            if step.chart == "heat":
                assert act.key == "canicule"
            if step.chart == "map":
                assert act.key in {"cartes_climatiques", "vent_pression"}


def test_minutes_sum_to_a_class_session() -> None:
    for act in ALL:
        total = sum(s.minutes for s in act.steps)
        assert 20 <= total <= 45, f"{act.key}: {total} min de questions seules"


def test_days_in_month_helper_parity() -> None:
    # Petit garde-fou : les cumuls mensuels de pluie en mm/mois dépendent du
    # nombre de jours du mois dans les conversions CDS.
    assert calendar.monthrange(2020, 2)[1] == 29
    assert calendar.monthrange(2021, 2)[1] == 28
