"""Bringing changes made in Candle on the web into a project file."""

import sqlite3

from PySide6.QtWidgets import QTextEdit

import pytest

from candle import cloud, sync
from candle.db import Project
from tests.test_cloud import FakeServers, signed_in, wait_for


@pytest.fixture
def servers(monkeypatch):
    fake = FakeServers()
    monkeypatch.setattr(cloud, "_http", fake)
    monkeypatch.setattr(cloud, "API_URL", "https://api")
    monkeypatch.setattr(cloud, "FIREBASE_API_KEY", "key")
    return fake


def qt_html(html):
    edit = QTextEdit()
    edit.setHtml(html)
    return edit.toHtml()


def make(tmp_path, name="book.candle"):
    p = Project.create(tmp_path / name, "Storm", "A. Writer")
    ch = p.list("chapters")[0]["id"]
    scene = p.list("scenes")[0]["id"]
    p.save_scene_content(scene, qt_html("<p>It was a <b>dark</b> night.</p>"), "It was a dark night.")
    marta = p.insert("characters", name="Marta")
    p.update("scenes", scene, notes="my notes", pov_id=marta)
    ch2 = p.insert("chapters", title="Gone")
    p.insert("scenes", chapter_id=ch2, title="Doomed")
    return p, ch, scene


def web_edit(version, scene_id, chapter_id):
    """What Candle on the web saves: plain HTML, a changed and an added scene, a chapter deleted."""
    conn = sqlite3.connect(version)
    with conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("UPDATE scenes SET content = ?, words = 6, status = 'done' WHERE id = ?",
                     ("<p>It was a <b>dark</b> night.</p><p>Then <i>rain</i>.</p>", scene_id))
        conn.execute("DELETE FROM chapters WHERE id != ?", (chapter_id,))
        conn.execute("INSERT INTO scenes (chapter_id, title, content, words, position) "
                     "VALUES (?, 'Dawn', '<p>Light.</p>', 1, 5)", (chapter_id,))
    conn.close()


def test_fingerprint_ignores_how_the_text_was_saved(qapp, tmp_path):
    p, _, scene = make(tmp_path)
    before = sync.fingerprint(p)
    # The same words, saved as plain HTML (the web) instead of Qt's: no change.
    p.save_scene_content(scene, "<p>It was a <b>dark</b> night.</p>", "x")
    assert sync.fingerprint(p) == before
    p.set_meta("arch_premise", qt_html("<p>A keeper.</p>"))
    after_premise = sync.fingerprint(p)
    p.set_meta("arch_premise", "<p>A keeper.</p>")                     # same text, other HTML
    assert sync.fingerprint(p) == after_premise != before
    p.save_scene_content(scene, "<p>It was a dark night.</p>", "x")   # bold gone: a real change
    assert sync.fingerprint(p) != after_premise


def test_fingerprint_covers_everything_the_web_edits(qapp, tmp_path):
    p, _, scene = make(tmp_path)
    marta = p.list("characters")[0]["id"]
    changes = [
        lambda: p.update("characters", marta, name="Marta L."),
        lambda: p.set_answer(marta, "personal", 0, "Marta Lindqvist"),
        lambda: p.set_link(scene, "character", marta, True),
        lambda: p.insert("locations", name="Harbour"),
        lambda: p.insert("strands", name="The storm"),
        lambda: p.update("scenes", scene, scene_time="1903-10-01"),
        lambda: p.update("scenes", scene, notes="other notes"),
        lambda: p.set_meta("daily_goal", 500),
        lambda: p.add_revision(scene),
    ]
    for change in changes:
        before = sync.fingerprint(p)
        change()
        assert sync.fingerprint(p) != before
    before = sync.fingerprint(p)
    p.start_day()                                                    # Candle's own bookkeeping…
    sync.remember(p, "B9", "x")                                      # …doesn't count
    assert sync.fingerprint(p) == before
    p.close()


def test_adopt_version_takes_everything_and_keeps_the_days(qapp, tmp_path):
    p, ch, scene = make(tmp_path)
    version = p.snapshot(tmp_path / "web.candle")
    web_edit(version, scene, ch)
    conn = sqlite3.connect(version)
    with conn:
        conn.execute("UPDATE characters SET name = 'Marta L.'")
        conn.execute("INSERT INTO character_answers VALUES (1, 'conflict', 0, 'The light')")
        conn.execute("INSERT INTO meta VALUES ('arch_themes', '<p>Duty</p>') "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    conn.close()
    p.conn.execute("INSERT INTO daily VALUES ('2099-01-01', 42)")    # recorded only here
    cloud_id = p.cloud_id()
    conn = sqlite3.connect(version)
    with conn:
        conn.execute("DELETE FROM meta WHERE key = 'cloud_id'")           # even if the version lacks it
    conn.close()
    sync.adopt_version(p, version)
    assert p.get_meta("cloud_id") == cloud_id
    row = p.get("scenes", scene)
    assert "rain" in row["content"] and row["status"] == "done" and row["notes"] == "my notes"
    assert [c["name"] for c in p.list("characters")] == ["Marta L."]
    assert p.answers(p.list("characters")[0]["id"])[("conflict", 0)] == "The light"
    assert p.get_meta("arch_themes") == "<p>Duty</p>"
    assert [c["id"] for c in p.list("chapters")] == [ch]
    assert p.conn.execute("SELECT start_words FROM daily WHERE day = '2099-01-01'").fetchone()[0] == 42
    p.close()


def test_detach_makes_a_separate_project(qapp, tmp_path):
    p, _, _ = make(tmp_path)
    sync.remember(p, "B1", "x")
    cloud_id = p.cloud_id()
    copy = p.snapshot(tmp_path / "copy.candle")
    p.close()
    sync.detach(copy)
    q = Project(copy)
    assert q.cloud_id() != cloud_id and q.get_meta("cloud_base") is None
    q.close()


def test_opening_brings_in_web_changes(qapp, servers, tmp_path, monkeypatch):
    from candle import app as app_module
    from candle.app import MainWindow
    p, ch, scene = make(tmp_path)
    sync.remember(p, "APP1", sync.fingerprint(p))          # this file matched the cloud's APP1
    version = p.snapshot(tmp_path / "web.candle")
    path = p.path
    p.close()
    web_edit(version, scene, ch)
    servers.uploads["https://gcs/obj"] = (version.read_bytes(), {})
    servers.versions = [{"backup_id": "WEB1", "created": "2026-10-29T10:00:00+00:00", "source": "web", "size": 1},
                        {"backup_id": "APP1", "created": "2026-10-28T10:00:00+00:00", "source": "app", "size": 1}]
    asked = []
    monkeypatch.setattr(app_module.QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or
                        app_module.QMessageBox.StandardButton.Yes)

    window = MainWindow()
    window.session = signed_in()
    try:
        window.open_project(str(path))
        assert wait_for(lambda: window.project and "rain" in window.project.get("scenes", scene)["content"])
        assert "edited in Candle on the web" in asked[0]
        assert wait_for(lambda: window.project.get_meta("cloud_base") == "B1")   # then backed up again
        assert window.project.get("scenes", scene)["notes"] == "my notes"
        assert len(asked) == 1                                            # not asked again after reloading
    finally:
        window.close_project()
        window.close()


def test_no_question_when_this_file_changed_too(qapp, servers, tmp_path, monkeypatch):
    from candle import app as app_module
    from candle.app import MainWindow
    p, _, scene = make(tmp_path)
    sync.remember(p, "APP1", sync.fingerprint(p))
    p.save_scene_content(scene, "<p>Edited here as well.</p>", "x")        # changed since APP1
    path = p.path
    p.close()
    servers.versions = [{"backup_id": "WEB1", "created": "2026-10-29T10:00:00+00:00", "source": "web", "size": 1}]
    shown = []
    monkeypatch.setattr(app_module.QMessageBox, "question", lambda *a, **k: shown.append("question"))
    monkeypatch.setattr(app_module.QMessageBox, "exec", lambda box: shown.append(box.text()) or 0)
    window = MainWindow()
    window.session = signed_in()
    try:
        window.open_project(str(path))
        assert wait_for(lambda: shown)
        assert "edited in Candle on the web" in shown[0] and "Nothing is merged" in shown[0]
        assert "Edited here as well" in window.project.get("scenes", scene)["content"]   # untouched
    finally:
        window.close_project()
        window.close()
