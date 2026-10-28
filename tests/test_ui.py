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
