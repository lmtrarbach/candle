from PySide6.QtTest import QTest

from candle.app import MainWindow
from candle.db import Project


def test_scene_text_fits_editor_when_opened(tmp_path, qapp):
    """Regression: the text used to be laid out wider than the centred column
    when a scene was first opened, showing a horizontal scrollbar."""
    path = tmp_path / "novel.candle"
    project = Project.create(path, "Wrap test")
    scene = project.list("scenes")[0]["id"]
    project.save_scene_content(scene, "<p>" + "word " * 500 + "</p>", "word " * 500)
    project.close()

    window = MainWindow()
    window.resize(1920, 1080)
    window.show()
    window.open_project(str(path))
    window.chapters_view.select("scene", scene)
    QTest.qWait(50)
    edit = window.chapters_view.scene_panel.editor.edit
    try:
        assert edit.document().textWidth() <= edit.viewport().width()
        assert not edit.horizontalScrollBar().isVisible()
    finally:
        window.close_project()
        window.close()


def _open_window(path):
    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    window.open_project(str(path))
    return window


def test_save_button_writes_pending_text_immediately(tmp_path, qapp):
    from PySide6.QtCore import Qt

    path = tmp_path / "novel.candle"
    project = Project.create(path, "Save test")
    scene = project.list("scenes")[0]["id"]
    project.close()

    window = _open_window(path)
    try:
        window.chapters_view.select("scene", scene)
        edit = window.chapters_view.scene_panel.editor.edit
        QTest.keyClicks(edit, "Call me Ishmael.")
        window._update_save_state()
        assert window.save_label.text() == "Saving…"
        # Not yet written: autosave waits for a pause in typing.
        assert "Ishmael" not in window.project.get("scenes", scene)["content"]

        QTest.mouseClick(window.save_button, Qt.MouseButton.LeftButton)
        assert "Ishmael" in window.project.get("scenes", scene)["content"]
        assert window.save_label.text().startswith("Saved ✓")
        # Checkpointed: the .candle file alone holds the text, no pending WAL.
        wal = path.with_name(path.name + "-wal")
        assert not wal.exists() or wal.stat().st_size == 0
    finally:
        window.close_project()
        window.close()


def test_ctrl_s_saves_in_focus_mode(tmp_path, qapp):
    from PySide6.QtCore import Qt

    path = tmp_path / "novel.candle"
    project = Project.create(path, "Focus save")
    scene = project.list("scenes")[0]["id"]
    project.close()

    window = _open_window(path)
    try:
        window.chapters_view.select("scene", scene)
        window.toggle_focus()   # menu bar hidden: the shortcut must still work
        QTest.qWaitForWindowActive(window)
        edit = window.chapters_view.scene_panel.editor.edit
        edit.setFocus()
        QTest.keyClicks(edit, "Focused words.")
        QTest.keyClick(edit, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        assert "Focused words" in window.project.get("scenes", scene)["content"]
    finally:
        window.close_project()
        window.close()


def test_save_widgets_hidden_without_project(qapp):
    window = MainWindow()
    window.show()
    window._update_save_state()
    assert not window.save_button.isVisible()
    assert not window.save_label.isVisible()
    window.close()
