"""Read-only sqlite fallback for edit-state when no fresh XMP sidecar is
available (plan §7.2).

Reads darktable's `library.db` (its default location,
`~/.config/darktable/library.db`, is resolved by the caller from Lua's
`darktable.configuration.config_dir` - this module has no GUI access and
just takes a path) read-only via `file:...?mode=ro&immutable=0`, and copies
to a temp file first if the DB turns out to be locked by a running
darktable instance.

Output shape matches `xmp.parse_xmp_bytes`/`xmp.read_edit_state`:
`{"history_source": "db", "enabled_modules": [...], "iop_order": [...]}`,
except `history_source` is `"db"` here.

Ground truth for the schema: the `CREATE TABLE` statements for `history`,
`images`, and `module_order` in `src/common/database.c` at darktable
release-4.6.0, cross-checked against the `INSERT INTO main.history`
statement in `src/common/exif.cc` (darktable's own XMP-import path) to
confirm column semantics:

- `history.module` holds the **modversion** integer (name is historical,
  not a module id).
- `history.op_params` / `history.blendop_params` are BLOB columns holding
  the already-raw struct bytes - unlike XMP's text `darktable:params`,
  there is no base64/hex/gz decoding step for the DB path.
- `images.history_end`: same "num < history_end AND enabled" truncation
  convention as the XMP `darktable:history_end` attribute.
- `module_order.iop_list`: same `operation,instance,operation,instance,...`
  text serialization as XMP's `darktable:iop_order_list`
  (`dt_ioppr_serialize_text_iop_order_list`).
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .params_codec import decode_params


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=0"
    return sqlite3.connect(uri, uri=True)


def _open_with_lock_fallback(db_path: Path) -> tuple[sqlite3.Connection, Path | None]:
    """Open `db_path` read-only in place; if that fails (typically because
    a running darktable instance holds an exclusive lock), copy the DB
    (and any WAL/SHM siblings) to a temp directory and open the copy
    instead.

    Returns `(connection, temp_dir_or_None)`; callers must remove
    `temp_dir_or_None` after closing the connection.
    """
    try:
        conn = _connect_readonly(db_path)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        return conn, None
    except sqlite3.OperationalError:
        pass

    tmp_dir = Path(tempfile.mkdtemp(prefix="dt-ai-helper-dbfallback-"))
    tmp_path = tmp_dir / db_path.name
    shutil.copy2(db_path, tmp_path)
    for suffix in ("-wal", "-shm"):
        sibling = db_path.with_name(db_path.name + suffix)
        if sibling.exists():
            shutil.copy2(sibling, tmp_dir / sibling.name)
    conn = _connect_readonly(tmp_path)
    return conn, tmp_dir


def _parse_iop_list_text(text: str | None) -> list[tuple[str, int]]:
    if not text:
        return []
    parts = [p.strip() for p in text.split(",")]
    pairs: list[tuple[str, int]] = []
    for i in range(0, len(parts) - 1, 2):
        op = parts[i]
        if not op:
            continue
        try:
            instance = int(parts[i + 1])
        except ValueError:
            instance = 0
        pairs.append((op, instance))
    return pairs


def _read_iop_order(conn: sqlite3.Connection, image_id: int) -> list[tuple[str, int]]:
    try:
        row = conn.execute(
            "SELECT iop_list FROM main.module_order WHERE imgid = ?", (image_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return []
    return _parse_iop_list_text(row[0]) if row else []


def _read_edit_state(conn: sqlite3.Connection, image_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT history_end FROM main.images WHERE id = ?", (image_id,)
    ).fetchone()
    if row is None:
        return {"history_source": "db", "enabled_modules": [], "iop_order": []}

    history_end = row[0]
    if history_end is None:
        history_end = 1 << 30  # not recorded: treat every history row as active

    rows = conn.execute(
        "SELECT num, module, operation, op_params, enabled, blendop_params,"
        " blendop_version, multi_priority, multi_name"
        " FROM main.history WHERE imgid = ? ORDER BY num ASC",
        (image_id,),
    ).fetchall()

    best: dict[tuple[str, int], tuple] = {}
    order: list[tuple[str, int]] = []
    for r in rows:
        num = r[0]
        if num >= history_end:
            continue
        key = (r[2], r[7] or 0)  # (operation, multi_priority)
        if key not in best:
            order.append(key)
        best[key] = r  # last entry per key wins

    iop_order_pairs = _read_iop_order(conn, image_id)
    order_index = {pair: i for i, pair in enumerate(iop_order_pairs)}

    active = [best[k] for k in order]
    active.sort(key=lambda r: order_index.get((r[2], r[7] or 0), len(order_index) + r[0]))

    enabled_modules = []
    for (
        _num,
        modversion,
        operation,
        op_params,
        enabled,
        _blendop_params,
        _blendop_version,
        multi_priority,
        multi_name,
    ) in active:
        if not enabled:
            continue
        raw = bytes(op_params) if op_params is not None else None
        decoded = decode_params(operation, modversion, raw) if raw else None
        module_entry: dict[str, Any] = {
            "op": operation,
            "label": multi_name or operation,
            "enabled": bool(enabled),
            "multi_name": multi_name or "",
            "multi_priority": multi_priority or 0,
            "modversion": modversion,
            "params_decoded": decoded,
            "raw_params": raw.hex() if raw else None,
        }
        if decoded is None and raw:
            module_entry["note"] = f"decoder not available for {operation} modversion {modversion}"
        enabled_modules.append(module_entry)

    iop_order = [op for op, _instance in iop_order_pairs] or [r[2] for r in active]

    return {
        "history_source": "db",
        "enabled_modules": enabled_modules,
        "iop_order": iop_order,
    }


def read_edit_state(db_path: str | Path, image_id: int) -> dict[str, Any]:
    """Read the edit state for `image_id` out of `library.db` at `db_path`."""
    conn, tmp_dir = _open_with_lock_fallback(Path(db_path))
    try:
        return _read_edit_state(conn, image_id)
    finally:
        conn.close()
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
