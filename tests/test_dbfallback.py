"""Tests for helper/dt_ai_helper/dbfallback.py.

Builds a throwaway sqlite DB matching the subset of darktable's
`library.db` schema this module reads (see the module docstring for the
`CREATE TABLE` ground truth), and checks the fallback produces the same
shape / same collapsing rules as xmp.py, plus the locked-DB copy-to-temp
path.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from dt_ai_helper import dbfallback


def _make_library_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE main.images (id INTEGER PRIMARY KEY, history_end INTEGER);
        CREATE TABLE main.history (
            imgid INTEGER, num INTEGER, module INTEGER, operation VARCHAR(256),
            op_params BLOB, enabled INTEGER, blendop_params BLOB,
            blendop_version INTEGER, multi_priority INTEGER,
            multi_name VARCHAR(256), multi_name_hand_edited INTEGER
        );
        CREATE TABLE main.module_order (
            imgid INTEGER PRIMARY KEY, version INTEGER, iop_list VARCHAR
        );
        """
    )
    exposure_v1 = struct.pack("<iffffi", 0, 0.0, 0.5, 50.0, -4.0, 0)
    exposure_v2 = struct.pack("<iffffi", 0, 0.0, 1.25, 50.0, -4.0, 0)
    exposure_inst1 = struct.pack("<iffffi", 0, 0.0, -0.25, 50.0, -4.0, 0)
    crop = struct.pack("<ffffii", 0, 0, 1, 1, -1, -1)

    conn.execute("INSERT INTO main.images (id, history_end) VALUES (1, 3)")
    rows = [
        (1, 0, 6, "exposure", exposure_v1, 1, None, 7, 0, "", 0),
        (1, 1, 6, "exposure", exposure_inst1, 1, None, 7, 1, "vignette control", 1),
        (1, 2, 6, "exposure", exposure_v2, 1, None, 7, 0, "", 0),
        (1, 3, 1, "crop", crop, 1, None, 7, 0, "", 0),  # beyond history_end=3
    ]
    conn.executemany(
        "INSERT INTO main.history (imgid, num, module, operation, op_params, enabled,"
        " blendop_params, blendop_version, multi_priority, multi_name, multi_name_hand_edited)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute(
        "INSERT INTO main.module_order (imgid, version, iop_list) VALUES (1, 1, ?)",
        ("exposure,0,exposure,1,crop,0",),
    )
    conn.commit()
    conn.close()


def test_dbfallback_matches_xmp_shape_and_collapsing(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    _make_library_db(db_path)

    result = dbfallback.read_edit_state(db_path, image_id=1)

    assert result["history_source"] == "db"
    assert result["iop_order"] == ["exposure", "exposure", "crop"]
    assert len(result["enabled_modules"]) == 2

    inst0, inst1 = result["enabled_modules"]
    assert inst0["op"] == "exposure"
    assert inst0["multi_priority"] == 0
    assert inst0["params_decoded"]["exposure"] == 1.25  # last-wins collapse
    assert inst1["multi_name"] == "vignette control"
    assert inst1["params_decoded"]["exposure"] == -0.25

    # crop is beyond history_end and must be excluded
    assert all(m["op"] != "crop" for m in result["enabled_modules"])


def test_dbfallback_unknown_image_id_returns_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    _make_library_db(db_path)
    result = dbfallback.read_edit_state(db_path, image_id=999)
    assert result == {"history_source": "db", "enabled_modules": [], "iop_order": []}


def test_dbfallback_disabled_row_excluded(tmp_path: Path) -> None:
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE main.images (id INTEGER PRIMARY KEY, history_end INTEGER);
        CREATE TABLE main.history (
            imgid INTEGER, num INTEGER, module INTEGER, operation VARCHAR(256),
            op_params BLOB, enabled INTEGER, blendop_params BLOB,
            blendop_version INTEGER, multi_priority INTEGER,
            multi_name VARCHAR(256), multi_name_hand_edited INTEGER
        );
        """
    )
    conn.execute("INSERT INTO main.images (id, history_end) VALUES (1, 1)")
    conn.execute(
        "INSERT INTO main.history VALUES (1, 0, 1, 'sharpen', ?, 0, NULL, 7, 0, '', 0)",
        (struct.pack("<fff", 2.0, 0.5, 0.5),),
    )
    conn.commit()
    conn.close()

    result = dbfallback.read_edit_state(db_path, image_id=1)
    assert result["enabled_modules"] == []


def test_dbfallback_copies_locked_db_to_temp(tmp_path: Path, monkeypatch) -> None:
    """Simulate a locked DB (opening read-only raises OperationalError) and
    verify the module falls back to copying it to a temp file rather than
    raising."""
    db_path = tmp_path / "library.db"
    _make_library_db(db_path)

    real_connect = dbfallback._connect_readonly
    call_count = {"n": 0}

    def flaky_connect(path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(path)

    monkeypatch.setattr(dbfallback, "_connect_readonly", flaky_connect)

    result = dbfallback.read_edit_state(db_path, image_id=1)
    assert result["history_source"] == "db"
    assert len(result["enabled_modules"]) == 2
    assert call_count["n"] == 2  # first attempt failed, fallback succeeded
