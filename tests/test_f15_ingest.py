"""Round 15 — observation-file intake: validate, then organize.

The owner keeps thousands of observation JSON files outside the app's
folder. Before any of them moves, its structure must be checked, and the
move itself must never overwrite another document.
"""

import json

import pytest

from oms_core.services import ingest


def _doc(**overrides):
    doc = {
        "meta": {"estacion": "78486", "fecha": "14102023"},
        "horas": {"00Z": {"datos": {"temp_seco": "24"}, "observador": "AC"}},
    }
    doc.update(overrides)
    return doc


def _write(tmp_path, name, doc, *, raw=None):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ----------------------------------------------------------- validation rules


def test_a_well_formed_document_is_accepted():
    assert ingest.validate_document(_doc()) == ("78486", 2023, 10, 14)


@pytest.mark.parametrize(
    ("doc", "fragment"),
    [
        ({"horas": {"00Z": {}}}, "meta"),
        ({"meta": {"estacion": "78486", "fecha": "14102023"}}, "horas"),
        ({"meta": {"estacion": "", "fecha": "14102023"}, "horas": {"00Z": {}}},
         "estacion"),
        ({"meta": {"estacion": "78486"}, "horas": {"00Z": {}}}, "fecha"),
        ({"meta": {"estacion": "78486", "fecha": "2023-10-14"},
          "horas": {"00Z": {}}}, "DDMMYYYY"),
        ({"meta": {"estacion": "78486", "fecha": "14102324"},
          "horas": {"00Z": {}}}, "fuera de rango"),
        ({"meta": {"estacion": "78486", "fecha": "3122024"},
          "horas": {"00Z": {}}}, "DDMMYYYY"),
        ({"meta": {"estacion": "78486", "fecha": "31022024"},
          "horas": {"00Z": {}}}, "no es una fecha real"),
        ({"meta": {"estacion": "78486", "fecha": "14102023"}, "horas": {}}, "vacío"),
        ({"meta": {"estacion": "78486", "fecha": "14102023"},
          "horas": {"99Z": {}}}, "hora desconocida"),
        ({"meta": {"estacion": "78486", "fecha": "14102023"},
          "horas": {"00Z": {"datos": []}}}, "datos no es un objeto"),
        ({"meta": {"estacion": "78486", "fecha": "14102023"},
          "horas": {"00Z": {}}, "cli3074": []}, "cli3074"),
    ],
)
def test_broken_documents_are_rejected_with_a_reason(doc, fragment):
    with pytest.raises(ingest.IngestError) as exc:
        ingest.validate_document(doc)
    assert fragment in str(exc.value)


def test_a_non_json_file_is_rejected(tmp_path):
    path = _write(tmp_path, "roto.json", None, raw="{no es json")
    with pytest.raises(ingest.IngestError) as exc:
        ingest.candidate_from_file(path)
    assert "JSON inválido" in str(exc.value)


# ----------------------------------------------------------------- planning


def test_plan_routes_a_document_to_station_year_month(tmp_path):
    src = _write(tmp_path / "origen", "7848614102023.json", _doc())
    plan = ingest.plan_organization([src], tmp_path / "destino")
    assert plan.rejections == []
    _candidate, destination = plan.moves[0]
    assert destination == (
        tmp_path / "destino" / "synop" / "78486" / "2023" / "10"
        / "7848614102023.json"
    )


def test_plan_reports_invalid_files_instead_of_dropping_them(tmp_path):
    good = _write(tmp_path, "bueno.json", _doc())
    bad = _write(tmp_path, "malo.json", {"meta": {"estacion": "1"}})
    plan = ingest.plan_organization([good, bad], tmp_path / "destino")
    assert len(plan.moves) == 1
    assert len(plan.rejections) == 1
    assert plan.rejections[0].path == bad
    assert plan.total_seen == 2


def test_a_file_already_in_place_is_not_a_move(tmp_path):
    root = tmp_path / "destino"
    src = _write(root / "synop" / "78486" / "2023" / "10",
                 "7848614102023.json", _doc())
    plan = ingest.plan_organization([src], root)
    assert plan.moves == []
    assert len(plan.in_place) == 1


def test_an_existing_destination_is_a_collision_not_an_overwrite(tmp_path):
    src = _write(tmp_path / "origen", "7848614102023.json", _doc())
    other = _write(tmp_path / "destino" / "synop" / "78486" / "2023" / "10",
                   "7848614102023.json", _doc(horas={"21Z": {"datos": {}}}))
    plan = ingest.plan_organization([src], tmp_path / "destino")
    assert plan.moves == []
    assert len(plan.collisions) == 1
    assert other.read_text(encoding="utf-8")  # untouched


def test_scan_finds_every_json_under_a_root(tmp_path):
    _write(tmp_path / "a" / "b", "uno.json", _doc())
    _write(tmp_path / "a", "dos.json", _doc())
    (tmp_path / "a" / "nota.txt").write_text("x", encoding="utf-8")
    assert len(ingest.scan_json_files(tmp_path)) == 2


# -------------------------------------------------------------- applying


def test_apply_moves_the_files_and_leaves_the_origin_empty(tmp_path):
    src = _write(tmp_path / "origen", "7848614102023.json", _doc())
    plan = ingest.plan_organization([src], tmp_path / "destino")
    result = ingest.apply_plan(plan)
    assert result["moved"] == 1
    assert not src.exists()
    assert (tmp_path / "destino" / "synop" / "78486" / "2023" / "10"
            / "7848614102023.json").is_file()


def test_apply_never_overwrites_and_reports_the_collision(tmp_path):
    src = _write(tmp_path / "origen", "7848614102023.json", _doc())
    plan = ingest.plan_organization([src], tmp_path / "destino")
    destination = plan.moves[0][1]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('{"meta": {"estacion": "OTRO"}}', encoding="utf-8")
    result = ingest.apply_plan(plan)
    assert result["moved"] == 0
    assert result["failed"] == 1
    assert src.exists()  # the original is untouched, nothing was lost
    assert "OTRO" in destination.read_text(encoding="utf-8")
