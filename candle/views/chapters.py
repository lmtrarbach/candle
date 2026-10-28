from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QPlainTextEdit, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from ..widgets import CheckList, Debouncer, RichEditor, heading, hbox
from .base import View, confirm

STATUS_LABELS = {"todo": "To do", "progress": "In progress", "done": "Done"}
STATUS_MARKS = {"todo": ("○", "#9a9a9a"), "progress": ("◐", "#d9952b"), "done": ("●", "#3c9a5f")}

ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE, ID_ROLE = ROLE, ROLE + 1


def item_key(item):
    return (item.data(0, KIND_ROLE), item.data(0, ID_ROLE)) if item else None


def set_key(item, kind, row_id):
    item.setData(0, KIND_ROLE, kind)
    item.setData(0, ID_ROLE, row_id)


class ChapterPanel(QWidget):
    renamed = Signal(int)

    def __init__(self):
        super().__init__()
        self.project = None
        self.chapter_id = None
        self.saver = Debouncer(self.save)

        self.title = QLineEdit()
        self.title.setObjectName("titleEdit")
        self.title.setPlaceholderText("Chapter title")
        self.title.textEdited.connect(self._title_edited)
        self.stats = QLabel()
        self.stats.setObjectName("hint")

        self.reason = RichEditor("Why does this chapter exist? What changes between its beginning and end?")
        self.notes = RichEditor("Notes, ideas, research for this chapter…")
        for editor in (self.reason, self.notes):
            editor.changed.connect(self.saver.poke)
        tabs = QTabWidget()
        tabs.addTab(self.reason, "Purpose")
        tabs.addTab(self.notes, "Notes")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.stats)
        layout.addWidget(tabs, 1)

    def load(self, project, chapter_id):
        self.project, self.chapter_id = project, chapter_id
        row = project.get("chapters", chapter_id)
        self.title.setText(row["title"])
        self.reason.set_html(row["reason"])
        self.notes.set_html(row["notes"])
        scenes = project.list("scenes", chapter_id=chapter_id)
        words = sum(s["words"] for s in scenes)
        done = sum(1 for s in scenes if s["status"] == "done")
        self.stats.setText(f"{len(scenes)} scenes · {done} done · {words:,} words")

    def _title_edited(self):
        self.saver.poke()

    def save(self):
        if self.chapter_id is None:
            return
        self.project.update("chapters", self.chapter_id, title=self.title.text(),
                            reason=self.reason.html(), notes=self.notes.html())
        self.renamed.emit(self.chapter_id)


class ScenePanel(QWidget):
    changed = Signal(int)       # scene id; label/words/status may have changed
    full_view_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.project = None
        self.scene_id = None
        self.saver = Debouncer(self.save)

        # Header
        self.title = QLineEdit()
        self.title.setObjectName("titleEdit")
        self.title.setPlaceholderText("Scene title")
        self.title.textEdited.connect(self.saver.poke)
        self.status = QComboBox()
        for key, label in STATUS_LABELS.items():
            self.status.addItem(label, key)
        self.status.activated.connect(self._meta_changed)
        self.details_btn = QPushButton("Details ▸")
        self.details_btn.setCheckable(True)
        self.details_btn.setChecked(True)
        self.details_btn.toggled.connect(self._toggle_details)
        self.full_btn = QPushButton()
        self.full_btn.setCheckable(True)
        self.full_btn.clicked.connect(self.full_view_clicked)
        self.header = hbox(self.title, self.status, self.details_btn, self.full_btn)
        self.header.layout().setStretch(0, 1)

        # Editor
        self.editor = RichEditor("Once upon a time…")
        self.editor.changed.connect(self.saver.poke)

        # Details panel
        self.pov = QComboBox()
        self.pov.activated.connect(self._meta_changed)
        self.location = QComboBox()
        self.location.activated.connect(self._meta_changed)
        self.time = QLineEdit()
        self.time.setPlaceholderText("e.g. 1888-08-31 03:40")
        self.time.setToolTip("When the scene happens. Use YYYY-MM-DD HH:MM so the timeline can sort it.")
        self.time.textEdited.connect(self.saver.poke)
        self.characters = CheckList()
        self.strands = CheckList()
        self.objects = CheckList()
        self.characters.toggled.connect(lambda i, on: self._link("character", i, on))
        self.strands.toggled.connect(lambda i, on: self._link("strand", i, on))
        self.objects.toggled.connect(lambda i, on: self._link("object", i, on))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Notes for this scene…")
        self.notes.textChanged.connect(self.saver.poke)
        snapshot = QPushButton("Save revision")
        snapshot.setToolTip("Keep a copy of the current text that you can go back to later")
        snapshot.clicked.connect(self._snapshot)
        history = QPushButton("Revisions…")
        history.clicked.connect(self._show_revisions)

        details = QWidget()
        details.setObjectName("sidePanel")
        form = QFormLayout(details)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Point of view", self.pov)
        form.addRow("Location", self.location)
        form.addRow("Time", self.time)
        for label, widget in (("Characters", self.characters), ("Narrative strands", self.strands),
                              ("Objects", self.objects)):
            widget.setMinimumHeight(90)
            form.addRow(label, widget)
        form.addRow("Notes", self.notes)
        form.addRow(hbox(snapshot, history))
        self.details = QScrollArea()
        self.details.setWidgetResizable(True)
        self.details.setWidget(details)
        self.details.setMinimumWidth(240)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.details)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([900, 280])

        layout = QVBoxLayout(self)
        layout.addWidget(self.header)
        layout.addWidget(self.splitter, 1)
        self.set_view()

    def load(self, project, scene_id):
        self.project, self.scene_id = project, scene_id
        row = project.get("scenes", scene_id)
        self.title.setText(row["title"])
        self.status.setCurrentIndex(self.status.findData(row["status"]))
        self.editor.set_html(row["content"])
        self.time.setText(row["scene_time"])
        self.notes.blockSignals(True)
        self.notes.setPlainText(row["notes"])
        self.notes.blockSignals(False)

        characters = project.list("characters")
        self._fill_combo(self.pov, characters, row["pov_id"], "— none —")
        self._fill_combo(self.location, project.list("locations"), row["location_id"], "— none —")
        self.characters.populate([(c["id"], c["name"]) for c in characters], project.links(scene_id, "character"))
        self.strands.populate([(s["id"], s["name"]) for s in project.list("strands")], project.links(scene_id, "strand"))
        self.objects.populate([(o["id"], o["name"]) for o in project.list("objects")], project.links(scene_id, "object"))

    @staticmethod
    def _fill_combo(combo, rows, selected, none_label):
        combo.clear()
        combo.addItem(none_label, None)
        for r in rows:
            combo.addItem(r["name"] or "(unnamed)", r["id"])
        combo.setCurrentIndex(max(0, combo.findData(selected)))

    def save(self):
        if self.scene_id is None:
            return
        self.project.update(
            "scenes", self.scene_id,
            title=self.title.text(),
            status=self.status.currentData(),
            scene_time=self.time.text().strip(),
            notes=self.notes.toPlainText(),
            pov_id=self.pov.currentData(),
            location_id=self.location.currentData(),
        )
        self.project.save_scene_content(self.scene_id, self.editor.html(), self.editor.plain())
        self.changed.emit(self.scene_id)

    def _meta_changed(self):
        self.saver.poke()
        self.saver.flush()

    def _link(self, kind, target_id, on):
        self.project.set_link(self.scene_id, kind, target_id, on)

    def _toggle_details(self, on):
        self.details.setVisible(on)
        self.details_btn.setText("Details ▸" if on else "◂ Details")

    def _snapshot(self):
        self.saver.flush()
        self.project.add_revision(self.scene_id)
        self.window().statusBar().showMessage("Revision saved.", 3000)

    def _show_revisions(self):
        self.saver.flush()
        dialog = RevisionsDialog(self.project, self.scene_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.restored is not None:
            self.load(self.project, self.scene_id)
            self.changed.emit(self.scene_id)

    def set_view(self, full=False, focus=False):
        """full: editor fills the window; focus: also hide header and toolbar."""
        self.header.setVisible(not focus)
        self.editor.toolbar.setVisible(not focus)
        self.details_btn.setVisible(not full)
        self.details.setVisible(not (full or focus) and self.details_btn.isChecked())
        self.full_btn.setChecked(full)
        self.full_btn.setText("Exit full view" if full else "Full view")
        self.full_btn.setToolTip(("Show the side panels again" if full else
                                  "Give the whole window to the text") + "  (Ctrl+Shift+F)")


class RevisionsDialog(QDialog):
    def __init__(self, project, scene_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scene revisions")
        self.resize(820, 560)
        self.project, self.scene_id = project, scene_id
        self.restored = None

        self.list = QListWidget()
        self.preview = QTextBrowser()
        self.list.currentItemChanged.connect(self._preview)
        restore = QPushButton("Restore this revision")
        restore.clicked.connect(self._restore)
        delete = QPushButton("Delete")
        delete.clicked.connect(self._delete)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        splitter = QSplitter()
        splitter.addWidget(self.list)
        splitter.addWidget(self.preview)
        splitter.setSizes([240, 580])
        layout = QVBoxLayout(self)
        hint = QLabel("Restoring first saves the current text as a revision, so nothing is lost.")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        layout.addWidget(splitter, 1)
        layout.addWidget(hbox(restore, delete, None, buttons))
        self._fill()

    def _fill(self):
        self.list.clear()
        for rev in self.project.revisions(self.scene_id):
            item = QListWidgetItem(f"{rev['created']}  ·  {rev['words']:,} words")
            item.setData(ROLE, rev["id"])
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.preview.setPlainText("No revisions yet. Use “Save revision” to keep a copy of a scene.")

    def _current(self):
        item = self.list.currentItem()
        return self.project.get("scene_revisions", item.data(ROLE)) if item else None

    def _preview(self, *_):
        rev = self._current()
        self.preview.setHtml(rev["content"] if rev else "")

    def _restore(self):
        rev = self._current()
        if rev is None:
            return
        self.project.add_revision(self.scene_id)
        self.project.update("scenes", self.scene_id, content=rev["content"], words=rev["words"])
        self.restored = rev["id"]
        self.accept()

    def _delete(self):
        rev = self._current()
        if rev and confirm(self, "Delete revision", "Delete this revision?"):
            self.project.delete("scene_revisions", rev["id"])
            self._fill()


class ChaptersView(View):
    full_view_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Chapters & scenes", "Words"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.tree.currentItemChanged.connect(self._selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)

        add_chapter = QPushButton("+ Chapter")
        add_chapter.clicked.connect(self.add_chapter)
        add_scene = QPushButton("+ Scene")
        add_scene.clicked.connect(self.add_scene)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete)
        up = QPushButton("↑")
        up.clicked.connect(lambda: self.move(-1))
        down = QPushButton("↓")
        down.clicked.connect(lambda: self.move(1))
        for b in (up, down):
            b.setMaximumWidth(36)

        self.left = QWidget()
        self.left.setObjectName("sidePanel")
        lv = QVBoxLayout(self.left)
        lv.addWidget(heading("Chapters"))
        lv.addWidget(self.tree, 1)
        lv.addWidget(hbox(add_chapter, add_scene, None, up, down))
        lv.addWidget(hbox(delete, None))

        self.chapter_panel = ChapterPanel()
        self.chapter_panel.renamed.connect(self._refresh_chapter)
        self.scene_panel = ScenePanel()
        self.scene_panel.changed.connect(self._scene_changed)
        self.scene_panel.full_view_clicked.connect(self.full_view_requested)
        empty = QLabel("Select a chapter or scene, or create a new one.")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setObjectName("hint")
        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(self.chapter_panel)
        self.stack.addWidget(self.scene_panel)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.left)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([280, 1000])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

    # -- tree -------------------------------------------------------------
    def reload(self):
        self.flush()
        current = self._current_key()
        self.tree.blockSignals(True)
        self.tree.clear()
        for n, ch in enumerate(self.project.list("chapters"), start=1):
            ch_item = QTreeWidgetItem()
            set_key(ch_item, "chapter", ch["id"])
            self.tree.addTopLevelItem(ch_item)
            total = 0
            for sc in self.project.list("scenes", chapter_id=ch["id"]):
                sc_item = QTreeWidgetItem(ch_item)
                set_key(sc_item, "scene", sc["id"])
                self._label_scene(sc_item, sc)
                total += sc["words"]
            self._label_chapter(ch_item, ch, n, total)
            ch_item.setExpanded(True)
        self.tree.blockSignals(False)
        if current:
            self.select(*current)
        else:
            self._show(None)

    def shown(self):
        # Entities may have been renamed elsewhere; refresh the open scene's choices.
        if self.stack.currentWidget() is self.scene_panel and self.scene_panel.scene_id:
            self.scene_panel.saver.flush()
            self.scene_panel.load(self.project, self.scene_panel.scene_id)

    def _label_chapter(self, item, ch, number, words):
        item.setText(0, f"{number}. {ch['title'] or 'Untitled chapter'}")
        item.setText(1, f"{words:,}")
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

    def _label_scene(self, item, sc):
        mark, color = STATUS_MARKS.get(sc["status"], STATUS_MARKS["todo"])
        item.setText(0, f"{mark}  {sc['title'] or 'Untitled scene'}")
        item.setForeground(0, QBrush(QColor(color)) if sc["status"] != "todo" else QBrush())
        item.setToolTip(0, STATUS_LABELS.get(sc["status"], ""))
        item.setText(1, f"{sc['words']:,}")

    def _find(self, kind, row_id):
        for i in range(self.tree.topLevelItemCount()):
            ch = self.tree.topLevelItem(i)
            if item_key(ch) == (kind, row_id):
                return ch
            for j in range(ch.childCount()):
                if item_key(ch.child(j)) == (kind, row_id):
                    return ch.child(j)
        return None

    def _current_key(self):
        return item_key(self.tree.currentItem())

    def select(self, kind, row_id):
        item = self._find(kind, row_id)
        if item:
            self.tree.setCurrentItem(item)
            self._show(item)
        else:
            self._show(None)

    def open_scene(self, scene_id):
        self.select("scene", scene_id)
        self.scene_panel.editor.edit.setFocus()

    def _selected(self, item, _previous):
        self.flush()
        self._show(item)

    def _show(self, item):
        key = item_key(item)
        if key is None:
            self.chapter_panel.chapter_id = self.scene_panel.scene_id = None
            self.stack.setCurrentIndex(0)
        elif key[0] == "chapter":
            self.scene_panel.scene_id = None
            self.chapter_panel.load(self.project, key[1])
            self.stack.setCurrentWidget(self.chapter_panel)
        else:
            self.chapter_panel.chapter_id = None
            self.scene_panel.load(self.project, key[1])
            self.stack.setCurrentWidget(self.scene_panel)

    def _refresh_chapter(self, chapter_id):
        item = self._find("chapter", chapter_id)
        if item:
            ch = self.project.get("chapters", chapter_id)
            words = sum(s["words"] for s in self.project.list("scenes", chapter_id=chapter_id))
            self._label_chapter(item, ch, self.tree.indexOfTopLevelItem(item) + 1, words)

    def _scene_changed(self, scene_id):
        item = self._find("scene", scene_id)
        if item:
            sc = self.project.get("scenes", scene_id)
            self._label_scene(item, sc)
            self._refresh_chapter(sc["chapter_id"])
        self.project_changed.emit()

    def flush(self):
        self.chapter_panel.saver.flush()
        self.scene_panel.saver.flush()

    # -- actions ----------------------------------------------------------
    def _selected_chapter_id(self):
        key = self._current_key()
        if key is None:
            return None
        if key[0] == "chapter":
            return key[1]
        return self.project.get("scenes", key[1])["chapter_id"]

    def add_chapter(self):
        self.flush()
        n = len(self.project.list("chapters")) + 1
        chapter_id = self.project.insert("chapters", title=f"Chapter {n}")
        self.reload()
        self.select("chapter", chapter_id)
        self.chapter_panel.title.setFocus()
        self.chapter_panel.title.selectAll()

    def add_scene(self):
        self.flush()
        chapter_id = self._selected_chapter_id()
        if chapter_id is None:
            chapters = self.project.list("chapters")
            if not chapters:
                self.add_chapter()
                chapter_id = self._selected_chapter_id()
            else:
                chapter_id = chapters[-1]["id"]
        n = len(self.project.list("scenes", chapter_id=chapter_id)) + 1
        scene_id = self.project.insert("scenes", chapter_id=chapter_id, title=f"Scene {n}")
        self.reload()
        self.select("scene", scene_id)
        self.scene_panel.title.setFocus()
        self.scene_panel.title.selectAll()
        self.project_changed.emit()

    def delete(self):
        key = self._current_key()
        if key is None:
            return
        kind, row_id = key
        if kind == "chapter":
            text = "Delete this chapter and all of its scenes? This cannot be undone."
        else:
            text = "Delete this scene? This cannot be undone."
        if not confirm(self, f"Delete {kind}", text):
            return
        self.chapter_panel.saver.timer.stop()
        self.scene_panel.saver.timer.stop()
        self.chapter_panel.chapter_id = self.scene_panel.scene_id = None
        self.project.delete("chapters" if kind == "chapter" else "scenes", row_id)
        self.tree.setCurrentItem(None)
        self.reload()
        self.project_changed.emit()

    def move(self, delta):
        key = self._current_key()
        if key is None:
            return
        self.flush()
        table = "chapters" if key[0] == "chapter" else "scenes"
        if self.project.move(table, key[1], delta):
            self.reload()
        elif table == "scenes":
            # At the edge of its chapter: hop into the neighbouring chapter.
            chapters = [c["id"] for c in self.project.list("chapters")]
            i = chapters.index(self._selected_chapter_id()) + delta
            if 0 <= i < len(chapters):
                self.project.move_scene_to_chapter(key[1], chapters[i])
                if delta > 0:
                    # Arriving from above: put it first in the next chapter.
                    while self.project.move("scenes", key[1], -1):
                        pass
                self.reload()

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        menu.addAction("New chapter", self.add_chapter)
        menu.addAction("New scene", self.add_scene)
        if item and item_key(item)[0] == "scene":
            scene_id = item_key(item)[1]
            move_menu = menu.addMenu("Move to chapter")
            for n, ch in enumerate(self.project.list("chapters"), start=1):
                move_menu.addAction(
                    f"{n}. {ch['title']}",
                    lambda c=ch["id"]: self._move_to(scene_id, c),
                )
            status_menu = menu.addMenu("Status")
            for key, label in STATUS_LABELS.items():
                status_menu.addAction(label, lambda k=key: self._set_status(scene_id, k))
        if item:
            menu.addSeparator()
            menu.addAction("Delete", self.delete)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _move_to(self, scene_id, chapter_id):
        self.flush()
        self.project.move_scene_to_chapter(scene_id, chapter_id)
        self.reload()
        self.select("scene", scene_id)

    def _set_status(self, scene_id, status):
        self.flush()
        self.project.update("scenes", scene_id, status=status)
        if self.scene_panel.scene_id == scene_id:
            self.scene_panel.status.setCurrentIndex(self.scene_panel.status.findData(status))
        self._scene_changed(scene_id)

    def has_open_scene(self):
        return self.stack.currentWidget() is self.scene_panel and self.scene_panel.scene_id is not None

    def set_view(self, full=False, focus=False):
        self.left.setVisible(not (full or focus))
        self.scene_panel.set_view(full, focus)
