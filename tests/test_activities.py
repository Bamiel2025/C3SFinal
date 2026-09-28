"""
Vérifie trois choses sur les activités :

1. la structure attendue (4 étapes, corrigé, indice, minutes) ;
2. la cohérence **chiffrée** des corrigés avec les données pré-calculées —
   un corrigé qui contredit les CSV est pire qu'un corrigé absent ;
3. la charte de rédaction des 48 consignes et la qualité des sujets type
   brevet (contexte, documents numérotés, verbes d'action, barème).
"""

from __future__ import annotations

import calendar
import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from c3s2 import activities, config, store

ALL = activities.ACTIVITIES
ALLOWED_CHARTS = {"none", "climato", "ombro", "annual", "anomalies", "compare", "map", "heat", "schema", "figure"}


def test_twelve_activities_with_four_steps() -> None:
    assert len(ALL) == 12
    for act in ALL:
        assert len(act.steps) == 4, act.key
        assert act.title and act.introduction
        assert act.default_cities or act.key == "elnino"  # El Niño : boîte océanique, pas des villes
        for step in act.steps:
            assert step.title and step.instruction
            assert step.hint
            assert step.expected and len(step.expected) > 40
            assert step.chart in ALLOWED_CHARTS
            assert 1 <= step.minutes <= 20


def test_list_activities_hides_answers_without_code() -> None:
    hidden = activities.list_activities(with_answers=False)
    shown = activities.list_activities(with_answers=True)
    assert len(hidden) == len(shown) == 12
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
            if step.chart == "schema":
                assert act.key == "vents_courants"
            if step.chart == "figure":
                assert act.key == "elnino"


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


def test_vents_courants_values(temp: pd.DataFrame) -> None:
    answers = " ".join(_expected("vents_courants"))
    b = _clim(temp, "Bordeaux")
    m = _clim(temp, "Montréal")
    assert "6,7" in answers and "−9,1" in answers  # signe moins U+2212
    assert f"{b.max() - b.min():.1f}".replace(".", ",") in answers  # 15,0
    assert f"{m.max() - m.min():.1f}".replace(".", ",") in answers  # 30,7
    # Étés quasi identiques : le contraste vient de l'hiver.
    assert abs(b.max() - m.max()) < 0.5


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


def _nino_frame() -> pd.DataFrame:
    root = Path(__file__).resolve().parent.parent
    frame = pd.read_csv(
        root / "data" / "precomputed" / "nino34_sst.csv",
        sep=";", index_col=0, parse_dates=True,
    )
    frame.index = pd.to_datetime(frame.index)
    return frame


def test_elnino_values() -> None:
    answers = " ".join(_expected("elnino"))
    serie = _nino_frame().iloc[:, 0].sort_index()
    assert len(serie) >= 400  # 1991 à mi-2026
    assert "26,5" in answers and "29,5" in answers  # août 2025 et 2026
    gap = serie.loc["2026-08"].iloc[0] - serie.loc["2025-08"].iloc[0]
    assert round(float(gap), 1) == 3.0
    base = serie.loc["1991":"2020"].groupby(serie.loc["1991":"2020"].index.month).mean()
    anom25 = (serie.loc["2025"] - base[serie.loc["2025"].index.month].values).mean()
    anom26 = (serie.loc["2026"] - base[serie.loc["2026"].index.month].values).mean()
    assert anom25 < 0 < anom26  # 2025 froide, 2026 chaude


# --------------------------------------------------------------------------- #
# Charte de rédaction des 48 consignes
# --------------------------------------------------------------------------- #

INSTRUCTION_STEMS = (
    "relev", "repèr", "reper", "lis", "calc", "compar", "expli", "rel", "préd",
    "pred", "rédig", "redig", "concl", "décri", "decri", "identif", "localis",
    "justif", "observ", "constat", "class", "range", "additionn", "suppos",
    "suis", "choisis", "indiq", "donn", "note", "propose", "disting", "déterm",
    "determin", "confront", "mesur", "affiche",
)

#: Ce qu'une consigne ne doit jamais livrer : la réponse attendue.
FORBIDDEN_IN_INSTRUCTIONS = {
    "ocean_continent": ("8,8", "17,9", "14,5"),
    "cycle_eau": ("600", "280", "250 mm"),
    "rechauffement": ("10,7", "12,2", "1,6 °C"),
    "cartes_climatiques": ("26 °C", "+16", "1019"),
    "vent_pression": ("1024", "996", "1019"),
    "latitude": ("21,5", "4,3", "17 °C", "13,6"),
    "avant_apres": ("10,5", "11,5", "+1 °C"),
    "pluies_europe": ("≈ 5", "−63", "−22", "153 mm"),
    "regimes_monde": ("1,7", "15,3", "19,7"),
    "portrait_climat": ("820", "15,0", "47 mm", "181 mm"),
    "vents_courants": ("15,8", "30,7", "16 °C"),
    "elnino": ("3,0 °C", "−0,4", "+0,9"),
}


def _norm(word: str) -> str:
    decomposed = unicodedata.normalize("NFKD", word.strip("«»\"' ").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def test_every_instruction_starts_with_an_action_verb() -> None:
    for act in ALL:
        for step in act.steps:
            first = _norm(step.instruction.split(" ")[0])
            assert any(first.startswith(s) for s in INSTRUCTION_STEMS), (
                f"{act.key} : la consigne commence par {first!r}"
            )


def test_one_question_at_most_per_step() -> None:
    for act in ALL:
        for step in act.steps:
            assert step.instruction.count("?") <= 1, f"{act.key} : {step.instruction}"


def test_instructions_do_not_leak_the_answer() -> None:
    for key, forbidden in FORBIDDEN_IN_INSTRUCTIONS.items():
        act = activities.get(key)
        text = " ".join(s.instruction for s in act.steps)
        for value in forbidden:
            assert value not in text, f"{key} : la consigne annonce {value!r}"


# --------------------------------------------------------------------------- #
# Sujets type brevet (rechauffement et elnino)
# --------------------------------------------------------------------------- #


def test_exam_only_where_planned() -> None:
    assert [a.key for a in ALL if a.exam is not None] == ["rechauffement", "elnino"]


def test_exam_passes_the_quality_gate() -> None:
    for act in ALL:
        if act.exam is None:
            continue
        assert activities.validate_exam(act.exam) == [], act.key


def test_exam_answers_hidden_without_code() -> None:
    hidden = {d["key"]: d for d in activities.list_activities(with_answers=False)}
    shown = {d["key"]: d for d in activities.list_activities(with_answers=True)}
    for key in ("rechauffement", "elnino"):
        hidden_q = hidden[key]["exam"]["questions"][0]
        shown_q = shown[key]["exam"]["questions"][0]
        assert "expected" not in hidden_q and "attendu" not in hidden_q
        assert "expected" in shown_q and "attendu" in shown_q
        assert hidden[key]["exam"]["questions"][0].get("points") is not None
        assert shown_q["points"] >= 1
        total = sum(q["points"] for q in shown[key]["exam"]["questions"])
        assert shown[key]["exam"]["points"] == total


def test_exam_documents_are_renderable() -> None:
    root = Path(__file__).resolve().parent.parent
    for act in ALL:
        if act.exam is None:
            continue
        for doc in act.exam.documents:
            assert doc.chart in {"annual", "anomalies", "figure", "table", "none"}
            if doc.chart == "figure":
                assert (root / "public" / "assets" / "figures" / doc.file).exists(), doc.file
            if doc.chart == "table":
                assert len(doc.table) >= 2
                assert len({len(row) for row in doc.table}) == 1


def test_rechauffement_exam_table_matches_data(temp: pd.DataFrame) -> None:
    doc = next(d for d in activities.get("rechauffement").exam.documents if d.chart == "table")
    annual = temp["Paris"].resample("YE").mean()
    annual.index = annual.index.year
    for label, value in doc.table[1:]:
        start, end = (int(x) for x in label.split("-"))
        quoted = f"{annual.loc[start:end].mean():.1f}".replace(".", ",")
        assert value == f"{quoted} °C", f"{label} : {value} ≠ {quoted} °C"
    answers = " ".join(q.expected for q in activities.get("rechauffement").exam.questions)
    assert "10,5 °C" in answers and "11,5 °C" in answers  # normales comparées


def _scalar(value) -> float:
    """Valeur unique, qu'elle soit un scalaire ou une Series d'un élément."""
    return float(value.iloc[0]) if hasattr(value, "iloc") else float(value)


def test_elnino_exam_table_matches_data() -> None:
    doc = next(d for d in activities.get("elnino").exam.documents if d.chart == "table")
    table = {label: value for label, value in doc.table[1:]}
    serie = _nino_frame().iloc[:, 0].sort_index()
    base = serie.loc["1991":"2020"].groupby(serie.loc["1991":"2020"].index.month).mean()
    assert table["Août 2025"] == f"{_scalar(serie.loc['2025-08']):.1f}".replace(".", ",") + " °C"
    assert table["Août 2026"] == f"{_scalar(serie.loc['2026-08']):.1f}".replace(".", ",") + " °C"
    assert table["Normale de août 1991-2020"] == f"{_scalar(base[8]):.1f}".replace(".", ",") + " °C"
    djf = serie.loc["2023-12":"2024-02"]
    anom = float((djf - base[djf.index.month].values).mean())
    assert table["Anomalie moyenne de l'hiver 2023-2024"] == f"+{anom:.1f}".replace(".", ",") + " °C"
    answers = " ".join(q.expected for q in activities.get("elnino").exam.questions)
    assert "3,0 °C" in answers  # écart d'un août à l'autre
    assert "+2,6" in answers  # anomalie d'août 2026 (ou +2,7 selon l'arrondi)
