"""Bringing changes made in Candle on the web into a project file.

Candle on the web edits a project's chapters and scenes only, and saves a new
cloud version. When the project is opened here, Candle compares:

- `cloud_base` (project meta): the cloud version this file last matched, set
  after each backup and after loading web changes;
- `cloud_fingerprint`: a hash of the chapters and scenes at that moment.

If the newest cloud version came from the web and this file's chapters and
scenes are unchanged since `cloud_base`, the web's chapters and scenes can be
brought in (`adopt_writing`), keeping everything else in the file. If both
changed, nothing is merged: the web version can be saved as its own file.
"""

import hashlib
import json
import sqlite3

from . import richtext


def fingerprint(project):
    """A hash of the chapters and scenes as text (what the web can change).
    Scene text is compared as Candle's paragraph model, not raw HTML, so the
    same words saved by the web and by Candle's editor count as the same."""
    h = hashlib.sha256()
    for row in project.conn.execute("SELECT id, title, position FROM chapters ORDER BY id"):
        h.update(json.dumps(["c", *row]).encode())
    for row in project.conn.execute(
            "SELECT id, chapter_id, title, status, position, content FROM scenes ORDER BY id"):
        paras = [[p.kind, p.align, [[r.text, r.bold, r.italic, r.underline, r.strike] for r in p.runs if r.text]]
                 for p in richtext.non_empty(richtext.parse(row[5]))]
        h.update(json.dumps(["s", *row[:5], paras]).encode())
    return h.hexdigest()


def remember(project, backup_id, print_):
    """Record that this file matches cloud version `backup_id`."""
    project.set_meta("cloud_base", backup_id)
    project.set_meta("cloud_fingerprint", print_)


def unchanged_since_sync(project):
    return bool(project.get_meta("cloud_base")) and project.get_meta("cloud_fingerprint") == fingerprint(project)


def adopt_writing(project, version_path):
    """Make this project's chapters and scenes those of the version at
    `version_path` (written on the web). Ids are shared, so a scene keeps its
    notes, POV, location, links and revisions here; scenes and chapters the
    web deleted are deleted, as in Candle. Only safe when this file's chapters
    and scenes haven't changed since that version's base (see module doc)."""
    other = sqlite3.connect(f"file:{version_path}?mode=ro", uri=True)
    try:
        chapters = other.execute("SELECT id, title, position FROM chapters").fetchall()
        scenes = other.execute(
            "SELECT id, chapter_id, title, status, content, words, position FROM scenes").fetchall()
    finally:
        other.close()
    conn = project.conn
    with conn:
        for chapter in chapters:
            conn.execute("INSERT INTO chapters (id, title, position) VALUES (?, ?, ?) ON CONFLICT(id) DO "
                         "UPDATE SET title = excluded.title, position = excluded.position", chapter)
        for scene in scenes:
            conn.execute(
                "INSERT INTO scenes (id, chapter_id, title, status, content, words, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET chapter_id = excluded.chapter_id, "
                "title = excluded.title, status = excluded.status, content = excluded.content, "
                "words = excluded.words, position = excluded.position", scene)
        keep_scenes = [s[0] for s in scenes] or [-1]
        keep_chapters = [c[0] for c in chapters] or [-1]
        conn.execute(f"DELETE FROM scenes WHERE id NOT IN ({','.join('?' * len(keep_scenes))})", keep_scenes)
        conn.execute(f"DELETE FROM chapters WHERE id NOT IN ({','.join('?' * len(keep_chapters))})", keep_chapters)


def detach(version_path):
    """Make a downloaded version its own project: its own cloud backups, no sync state."""
    conn = sqlite3.connect(version_path)
    try:
        with conn:
            conn.execute("DELETE FROM meta WHERE key IN ('cloud_id', 'cloud_base', 'cloud_fingerprint')")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
