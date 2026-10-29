"""Bringing changes made in Candle on the web into a project file.

Candle on the web edits everything Candle does and saves a new cloud version.
When the project is opened here, Candle compares:

- `cloud_base` (project meta): the cloud version this file last matched, set
  after each backup and after loading web changes;
- `cloud_fingerprint`: a hash, at that moment, of everything the web can edit.

If the newest cloud version came from the web and this file is unchanged
since `cloud_base`, the web version replaces this file's contents
(`adopt_version`); nothing here is lost, since nothing here changed. If both
changed, nothing is merged: the web version can be saved as its own file.
"""

import hashlib
import json
import sqlite3

from . import richtext

# What Candle on the web edits (candle_premium/server/app/webedit.py).
META_KEYS = ("title", "author", "language", "target_words", "daily_goal",
             "arch_premise", "arch_fabula", "arch_setting", "arch_themes", "arch_notes")
RICH_META = {k for k in META_KEYS if k.startswith("arch_")}
TABLES = {
    # table: (columns, rich-text columns), rows ordered by their key columns
    "chapters": ("id, title, reason, notes, position", {"reason", "notes"}),
    "scenes": ("id, chapter_id, title, content, notes, status, pov_id, location_id, scene_time, position",
               {"content"}),
    "scene_links": ("scene_id, kind, target_id", set()),
    "scene_revisions": ("id, scene_id", set()),
    "characters": ("id, name, role, description, position", {"description"}),
    "character_answers": ("character_id, section, question, answer", set()),
    "locations": ("id, name, nation, state, city, description, position", {"description"}),
    "objects": ("id, name, description, position", {"description"}),
    "strands": ("id, name, description, position", {"description"}),
}


def _text(rich):
    """Rich text as Candle's paragraph model: the same words saved by the web
    and by Candle's editor (different HTML) compare equal."""
    return [[p.kind, p.align, [[r.text, r.bold, r.italic, r.underline, r.strike] for r in p.runs if r.text]]
            for p in richtext.non_empty(richtext.parse(rich or ""))]


def fingerprint(project):
    """A hash of everything Candle on the web can change."""
    h = hashlib.sha256()
    meta = dict(project.conn.execute("SELECT key, value FROM meta").fetchall())
    for key in META_KEYS:
        value = meta.get(key)
        value = _text(value) if key in RICH_META else ("" if value is None else str(value))
        h.update(json.dumps(["meta", key, value]).encode())
    for table, (columns, rich) in TABLES.items():
        names = [c.strip() for c in columns.split(",")]
        for row in project.conn.execute(f"SELECT {columns} FROM {table} ORDER BY {columns}"):
            values = [_text(v) if name in rich else v for name, v in zip(names, row)]
            h.update(json.dumps([table, *values]).encode())
    return h.hexdigest()


def remember(project, backup_id, print_):
    """Record that this file matches cloud version `backup_id`."""
    project.set_meta("cloud_base", backup_id)
    project.set_meta("cloud_fingerprint", print_)


def unchanged_since_sync(project):
    return bool(project.get_meta("cloud_base")) and project.get_meta("cloud_fingerprint") == fingerprint(project)


def adopt_version(project, version_path):
    """Make this project's contents those of the version at `version_path`
    (written on the web from this file's last cloud version). Only safe when
    this file is unchanged since then (see module doc). This file's cloud id
    (its link to its backups) and the days' starting word counts recorded
    here are kept."""
    days = project.conn.execute("SELECT day, start_words FROM daily").fetchall()
    cloud_id = project.get_meta("cloud_id")
    project.conn.commit()
    other = sqlite3.connect(f"file:{version_path}?mode=ro", uri=True)
    try:
        other.backup(project.conn)
    finally:
        other.close()
    with project.conn:
        project.conn.executemany("INSERT OR IGNORE INTO daily (day, start_words) VALUES (?, ?)", days)
    if cloud_id:
        project.set_meta("cloud_id", cloud_id)


def detach(version_path):
    """Make a downloaded version its own project: its own cloud backups, no sync state."""
    conn = sqlite3.connect(version_path)
    try:
        with conn:
            conn.execute("DELETE FROM meta WHERE key IN ('cloud_id', 'cloud_base', 'cloud_fingerprint')")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
