"""
Tests de contrat de l'API (`/api/*`).

Aucun réseau n'est requis : les séries viennent des CSV pré-calculés, les
cartes du répertoire `public/assets/maps`, les activités du code Python.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from c3s2 import config, server

client = TestClient(server.app)
TEACHER = config.teacher_code()


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"]


def test_config_masks_the_cds_key() -> None:
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()

    cds = body["cds"]
    assert "masked_key" in cds
    raw = cds.get("masked_key", "")
    key = config.resolve_cds_config().key or ""
    assert len(raw) <= 12
    if key:
        assert key not in r.text  # la clé complète n'apparaît jamais

    assert body["teacher_code_required"] is True
    # La valeur du code enseignant ne fuite jamais dans la réponse.
    if len(TEACHER) >= 4:
        assert TEACHER not in r.text
    assert list(body["reference_period"]) == list(config.REFERENCE_PERIOD)
    assert isinstance(body["precomputed"], list)


def test_places_catalog() -> None:
    r = client.get("/api/places")
    assert r.status_code == 200
    body = r.json()
    assert len(body["cities"]) >= 20
    assert len(body["maps"]) == 6
    assert body["variables"]
    assert body["domains"]

    names = {c["name"] for c in body["cities"]}
    assert {"Paris", "Brest", "Marseille"} <= names


def test_series_from_precomputed_data() -> None:
    r = client.get(
        "/api/series",
        params={
            "cities": "Paris,Brest",
            "variable": "2m_temperature",
            "start": 1991,
            "end": 2020,
            "source": "auto",
        },
    )
    assert r.status_code == 200
    body = r.json()

    meta = body["meta"]
    assert meta["start"] == 1991 and meta["end"] == 2020
    assert meta["unit"] == "°C"
    assert meta["source"] in {"precomputed", "cds", "simulated"}

    assert set(body["series"]) == {"Paris", "Brest"}
    paris = body["series"]["Paris"]
    dates, values = paris["dates"], paris["values"]
    assert dates[0].startswith("1991-01") and dates[-1].startswith("2020-12")
    assert len(dates) == len(values) == 360  # 30 ans × 12 mois
    assert all(isinstance(v, (int, float)) for v in values)
    assert -30 < min(values) < max(values) < 45

    assert "Paris" in body["stats"]
    stats = body["stats"]["Paris"]
    assert stats["n_points"] == 360
    clim = stats["climatology"]
    assert len(clim["months"]) == len(clim["values"]) == 12
    assert clim["reference"] == "1991-2020"
    lo, hi = min(clim["values"]), max(clim["values"])
    assert lo <= sum(clim["values"]) / 12 <= hi
    assert 3.0 <= lo <= 6.0 and 18.0 <= hi <= 22.0  # Paris : hiver froid, été chaud


def test_series_rejects_bad_source() -> None:
    r = client.get(
        "/api/series",
        params={"cities": "Paris", "source": "n_importe_quoi"},
    )
    assert r.status_code == 422


def test_activities_hide_answers_without_code() -> None:
    r = client.get("/api/activities")
    assert r.status_code == 200
    body = r.json()
    assert body["unlocked"] is False

    for act in body["activities"]:
        for step in act["steps"]:
            assert "expected" not in step
            assert step["instruction"]
            assert step["title"]


def test_activities_reveal_answers_with_code() -> None:
    r = client.get("/api/activities", params={"code": TEACHER})
    assert r.status_code == 200
    body = r.json()
    assert body["unlocked"] is True

    seen: set[str] = set()
    for act in body["activities"]:
        assert act["key"] not in seen
        seen.add(act["key"])
        assert len(act["steps"]) == 4
        for step in act["steps"]:
            assert step.get("expected"), f"corrigé manquant: {act['key']}"
            assert step.get("hint")


def test_teacher_unlock_wrong_code() -> None:
    r = client.post("/api/teacher/unlock", json={"code": "000000"})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_teacher_unlock_right_code() -> None:
    r = client.post("/api/teacher/unlock", json={"code": TEACHER})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_maps_catalog_and_payload() -> None:
    index = client.get("/assets/maps/index.json")
    assert index.status_code == 200
    maps = index.json()
    assert len(maps) == 6
    ids = {m["id"] for m in maps}
    assert {"t2m_janvier", "t2m_juillet", "mslp_janvier", "vent_janvier"} <= ids

    r = client.get("/api/maps/t2m_janvier")
    assert r.status_code == 200
    payload = r.json()
    assert payload["unit"] == "°C"
    assert len(payload["lat"]) == len(payload["z"])
    assert payload["area"][0] > payload["area"][2]  # ordre [N, O, S, E]


def test_map_unknown_id() -> None:
    r = client.get("/api/maps/inexistant")
    assert r.status_code in {404, 503}


def test_bundled_maps_copy() -> None:
    """La copie livrée avec le code contient les 6 cartes (repli Vercel)."""
    import json

    index_path = config.BUNDLED_MAPS_DIR / "index.json"
    assert index_path.is_file(), "lancez scripts/prepare_maps.py (sync_bundled)"
    bundled = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(bundled) == 6
    for entry in bundled:
        payload_path = config.BUNDLED_MAPS_DIR / f"{entry['id']}.json"
        assert payload_path.is_file()
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        assert payload["z"] and payload["lat"] and payload["lon"]


def test_maps_fallback_without_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans `public/` (cas Vercel), l'API sert la copie livrée : jamais 0 carte."""
    from c3s2 import fields

    monkeypatch.setattr(fields, "PUBLIC_MAPS_DIR", config.BUNDLED_MAPS_DIR / "inexistant")
    assert fields._maps_dir() == config.BUNDLED_MAPS_DIR
    assert len(fields.list_maps()) == 6
    assert fields.load_map("t2m_juillet")["unit"] == "°C"


def test_spa_serves_index_html() -> None:
    for path in ("/", "/activites/ocean_continent", "/cartes"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "text/html" in r.headers["content-type"]
        assert '<html lang="fr">' in r.text
        assert '<main id="main"' in r.text


def test_static_assets() -> None:
    for path in ("/assets/styles.css", "/assets/js/app.js", "/assets/js/charts.js"):
        r = client.get(path)
        assert r.status_code == 200, path


def test_unknown_api_route_is_404() -> None:
    r = client.get("/api/rien_quoi_que_ce_soit")
    assert r.status_code == 404


@pytest.mark.parametrize("code", ["", " ", "123", "abcd"])
def test_bad_teacher_codes(code: str) -> None:
    assert config.check_teacher_code(code) is False
