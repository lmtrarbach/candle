"""Project storage: one SQLite file per novel (extension .candle)."""

import datetime
import os
import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS chapters (
    id       INTEGER PRIMARY KEY,
    title    TEXT NOT NULL DEFAULT '',
    reason   TEXT NOT NULL DEFAULT '',
    notes    TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS scenes (
    id          INTEGER PRIMARY KEY,
    chapter_id  INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'todo',
    pov_id      INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    scene_time  TEXT NOT NULL DEFAULT '',
    words       INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS scene_revisions (
    id       INTEGER PRIMARY KEY,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    content  TEXT NOT NULL,
    words    INTEGER NOT NULL DEFAULT 0,
    created  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scene_links (
    scene_id  INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,          -- 'character' | 'strand' | 'object'
    target_id INTEGER NOT NULL,
    PRIMARY KEY (scene_id, kind, target_id)
);
CREATE TABLE IF NOT EXISTS characters (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    role        TEXT NOT NULL DEFAULT 'secondary',   -- 'main' | 'secondary'
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS character_answers (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    section      TEXT NOT NULL,
    question     INTEGER NOT NULL,
    answer       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (character_id, section, question)
);
CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    nation      TEXT NOT NULL DEFAULT '',
    state       TEXT NOT NULL DEFAULT '',
    city        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS objects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS strands (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS daily (
    day         TEXT PRIMARY KEY,
    start_words INTEGER NOT NULL
);
"""

SCHEMA_VERSION = "1"

# Ordering scope for each positioned table: rows are ordered among siblings
# sharing the same value of this column (None = whole table).
POSITION_SCOPE = {
    "chapters": None,
    "scenes": "chapter_id",
    "characters": None,
    "locations": None,
    "objects": None,
    "strands": None,
}

# Scene links point at these tables; used to clean up when targets go away.
LINK_KIND_TABLE = {"character": "characters", "strand": "strands", "object": "objects"}

STATUSES = ("todo", "progress", "done")

_IDENT = re.compile(r"^[a-z_]+$")
_WORD = re.compile(r"\w+(?:['’\-]\w+)*")


def count_words(text):
    return len(_WORD.findall(text))


def _ident(name):
    if not _IDENT.match(name):
        raise ValueError(f"bad identifier: {name!r}")
    return name


def _today():
    return datetime.date.today().isoformat()


class Project:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        if self.get_meta("schema_version") is None:
            self.set_meta("schema_version", SCHEMA_VERSION)

    @classmethod
    def create(cls, path, title, author=""):
        if os.path.exists(path):
            raise FileExistsError(path)
        project = cls(path)
        project.set_meta("title", title)
        project.set_meta("author", author)
        project.set_meta("created", datetime.datetime.now().isoformat(timespec="seconds"))
        chapter = project.insert("chapters", title="Chapter 1")
        project.insert("scenes", chapter_id=chapter, title="Scene 1")
        return project

    def close(self):
        self.conn.close()

    def checkpoint(self):
        """Fold the write-ahead log into the .candle file itself, so the file
        is complete on its own (safe to copy while the project is open)."""
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # -- meta -------------------------------------------------------------
    def get_meta(self, key, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, "" if value is None else str(value)),
        )

    @property
    def title(self):
        return self.get_meta("title", "") or self.path.stem

    # -- generic CRUD -----------------------------------------------------
    def get(self, table, row_id):
        return self.conn.execute(
            f"SELECT * FROM {_ident(table)} WHERE id = ?", (row_id,)
        ).fetchone()

    def list(self, table, **where):
        sql = f"SELECT * FROM {_ident(table)}"
        params = []
        if where:
            sql += " WHERE " + " AND ".join(f"{_ident(k)} = ?" for k in where)
            params = list(where.values())
        if table in POSITION_SCOPE:
            sql += " ORDER BY position, id"
        return self.conn.execute(sql, params).fetchall()

    def insert(self, table, **fields):
        if table in POSITION_SCOPE and "position" not in fields:
            fields["position"] = self._next_position(table, fields)
        cols = ", ".join(_ident(k) for k in fields)
        marks = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO {_ident(table)} ({cols}) VALUES ({marks})", list(fields.values())
        )
        return cur.lastrowid

    def update(self, table, row_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{_ident(k)} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE {_ident(table)} SET {sets} WHERE id = ?", [*fields.values(), row_id]
        )

    def delete(self, table, row_id):
        with self.conn:
            self.conn.execute("BEGIN")
            for kind, target in LINK_KIND_TABLE.items():
                if target == table:
                    self.conn.execute(
                        "DELETE FROM scene_links WHERE kind = ? AND target_id = ?",
                        (kind, row_id),
                    )
            self.conn.execute(f"DELETE FROM {_ident(table)} WHERE id = ?", (row_id,))

    def _next_position(self, table, fields):
        scope = POSITION_SCOPE[table]
        if scope:
            row = self.conn.execute(
                f"SELECT MAX(position) FROM {table} WHERE {scope} = ?", (fields[scope],)
            ).fetchone()
        else:
            row = self.conn.execute(f"SELECT MAX(position) FROM {table}").fetchone()
        return (row[0] or 0) + 1

    def move(self, table, row_id, delta):
        """Move a row up (delta=-1) or down (delta=+1) among its siblings.
        Returns True if it moved."""
        row = self.get(table, row_id)
        scope = POSITION_SCOPE[table]
        siblings = [r["id"] for r in (self.list(table, **{scope: row[scope]}) if scope else self.list(table))]
        i = siblings.index(row_id)
        j = i + delta
        if not 0 <= j < len(siblings):
            return False
        siblings[i], siblings[j] = siblings[j], siblings[i]
        self._renumber(table, siblings)
        return True

    def move_scene_to_chapter(self, scene_id, chapter_id):
        position = self._next_position("scenes", {"chapter_id": chapter_id})
        self.update("scenes", scene_id, chapter_id=chapter_id, position=position)

    def _renumber(self, table, ids):
        with self.conn:
            self.conn.execute("BEGIN")
            for pos, row_id in enumerate(ids, start=1):
                self.conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (pos, row_id))

    # -- scenes -----------------------------------------------------------
    def save_scene_content(self, scene_id, html, plain_text):
        self.update("scenes", scene_id, content=html, words=count_words(plain_text))

    def all_scenes(self):
        """Every scene in reading order, with its chapter's title and number."""
        return self.conn.execute(
            """SELECT s.*, c.title AS chapter_title, c.position AS chapter_position
               FROM scenes s JOIN chapters c ON c.id = s.chapter_id
               ORDER BY c.position, c.id, s.position, s.id"""
        ).fetchall()

    def links(self, scene_id, kind):
        return {
            r["target_id"]
            for r in self.conn.execute(
                "SELECT target_id FROM scene_links WHERE scene_id = ? AND kind = ?",
                (scene_id, kind),
            )
        }

    def all_links(self, kind):
        return self.conn.execute(
            "SELECT scene_id, target_id FROM scene_links WHERE kind = ?", (kind,)
        ).fetchall()

    def set_link(self, scene_id, kind, target_id, on):
        if kind not in LINK_KIND_TABLE:
            raise ValueError(kind)
        if on:
            self.conn.execute(
                "INSERT OR IGNORE INTO scene_links(scene_id, kind, target_id) VALUES (?, ?, ?)",
                (scene_id, kind, target_id),
            )
        else:
            self.conn.execute(
                "DELETE FROM scene_links WHERE scene_id = ? AND kind = ? AND target_id = ?",
                (scene_id, kind, target_id),
            )

    def add_revision(self, scene_id):
        scene = self.get("scenes", scene_id)
        return self.insert(
            "scene_revisions",
            scene_id=scene_id,
            content=scene["content"],
            words=scene["words"],
            created=datetime.datetime.now().isoformat(sep=" ", timespec="seconds"),
        )

    def revisions(self, scene_id):
        return self.conn.execute(
            "SELECT * FROM scene_revisions WHERE scene_id = ? ORDER BY id DESC", (scene_id,)
        ).fetchall()

    # -- characters -------------------------------------------------------
    def answers(self, character_id):
        return {
            (r["section"], r["question"]): r["answer"]
            for r in self.conn.execute(
                "SELECT * FROM character_answers WHERE character_id = ?", (character_id,)
            )
        }

    def set_answer(self, character_id, section, question, answer):
        self.conn.execute(
            "INSERT INTO character_answers(character_id, section, question, answer) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(character_id, section, question) "
            "DO UPDATE SET answer = excluded.answer",
            (character_id, section, question, answer),
        )

    # -- statistics -------------------------------------------------------
    def total_words(self):
        return self.conn.execute("SELECT COALESCE(SUM(words), 0) FROM scenes").fetchone()[0]

    def start_day(self):
        """Record today's starting word count (once per day)."""
        self.conn.execute(
            "INSERT OR IGNORE INTO daily(day, start_words) VALUES (?, ?)",
            (_today(), self.total_words()),
        )

    def words_today(self):
        self.start_day()
        row = self.conn.execute("SELECT start_words FROM daily WHERE day = ?", (_today(),)).fetchone()
        return self.total_words() - row[0]

    # -- backups ----------------------------------------------------------
    def backup(self, directory, keep=10):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        target = directory / f"{self.path.stem}-{stamp}.candle"
        dest = sqlite3.connect(str(target))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        old = sorted(directory.glob(f"{self.path.stem}-*.candle"))
        for stale in old[:-keep]:
            stale.unlink()
        return target
