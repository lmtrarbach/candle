from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from ..widgets import Debouncer, RichEditor, heading, hbox


class View(QWidget):
    """A page in the main window. Subclasses override reload() and flush()."""

    project_changed = Signal()   # emitted after edits that affect word counts etc.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None

    def set_project(self, project):
        self.project = project
        if project is not None:
            self.reload()

    def reload(self):
        pass

    def flush(self):
        """Write any pending edits to the project."""

    def shown(self):
        """Called whenever the user navigates to this page."""
        self.reload()


def confirm(parent, title, text):
    return QMessageBox.question(parent, title, text) == QMessageBox.StandardButton.Yes


class EntityView(View):
    """List of named entities on the left, editor for the selected one on the right."""

    table = ""
    singular = ""
    plural = ""
    intro = ""
    extra_fields = ()   # (column, label, placeholder)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        self.saver = Debouncer(self.save_current)

        # Left: list + buttons
        left = QWidget()
        left.setObjectName("sidePanel")
        lv = QVBoxLayout(left)
        lv.addWidget(heading(self.plural))
        if self.intro:
            intro = QLabel(self.intro)
            intro.setWordWrap(True)
            intro.setObjectName("hint")
            lv.addWidget(intro)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._selected)
        lv.addWidget(self.list, 1)
        add = QPushButton(f"Add {self.singular}")
        add.clicked.connect(self.add)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete)
        up = QPushButton("↑")
        up.setToolTip("Move up")
        up.clicked.connect(lambda: self.move(-1))
        down = QPushButton("↓")
        down.setToolTip("Move down")
        down.clicked.connect(lambda: self.move(1))
        for b in (up, down):
            b.setMaximumWidth(36)
        lv.addWidget(hbox(add, delete, None, up, down))

        # Right: form
        self.form = QWidget()
        fv = QVBoxLayout(self.form)
        self.name = QLineEdit()
        self.name.setObjectName("titleEdit")
        self.name.setPlaceholderText(f"{self.singular.capitalize()} name")
        self.name.textEdited.connect(self._name_edited)
        fv.addWidget(self.name)
        fields = QFormLayout()
        self.extras = {}
        for column, label, placeholder in self.extra_fields:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            edit.textEdited.connect(self.saver.poke)
            fields.addRow(label, edit)
            self.extras[column] = edit
        self.build_extra(fields)
        if fields.rowCount():
            fv.addLayout(fields)
        fv.addWidget(self.build_body(), 1)

        empty = QLabel(f"Select a {self.singular} on the left, or add a new one.")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setObjectName("hint")
        self.right = QStackedWidget()
        self.right.addWidget(empty)
        self.right.addWidget(self.form)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # -- hooks for subclasses --------------------------------------------
    def build_extra(self, form_layout):
        pass

    def build_body(self):
        self.description = RichEditor(f"Describe this {self.singular}…")
        self.description.changed.connect(self.saver.poke)
        return self.description

    def load_extra(self, row):
        pass

    def save_extra(self):
        return {}

    def label(self, row):
        return row["name"] or "(unnamed)"

    # -- behaviour --------------------------------------------------------
    def reload(self):
        self.flush()
        keep = self.current_id
        self.list.blockSignals(True)
        self.list.clear()
        for row in self.project.list(self.table):
            item = QListWidgetItem(self.label(row))
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.current_id = None
        self.select(keep)

    def shown(self):
        pass   # nothing outside this view changes our list

    def select(self, row_id):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == row_id:
                self.list.setCurrentRow(i)
                return
        self._load(None)

    def _selected(self, item, _previous=None):
        self.flush()
        self._load(item.data(Qt.ItemDataRole.UserRole) if item else None)

    def _load(self, row_id):
        self.current_id = row_id
        row = self.project.get(self.table, row_id) if row_id else None
        if row is None:
            self.current_id = None
            self.right.setCurrentIndex(0)
            return
        self.name.setText(row["name"])
        for column, edit in self.extras.items():
            edit.setText(row[column])
        self.description.set_html(row["description"])
        self.load_extra(row)
        self.right.setCurrentIndex(1)

    def _name_edited(self):
        item = self.list.currentItem()
        if item:
            item.setText(self.name.text() or "(unnamed)")
        self.saver.poke()

    def flush(self):
        self.saver.flush()

    def save_current(self):
        if self.current_id is None or self.project is None:
            return
        fields = {"name": self.name.text(), "description": self.description.html()}
        fields.update({c: e.text() for c, e in self.extras.items()})
        fields.update(self.save_extra())
        self.project.update(self.table, self.current_id, **fields)
        item = self.list.currentItem()
        if item:
            item.setText(self.label(self.project.get(self.table, self.current_id)))

    def add(self):
        self.flush()
        row_id = self.project.insert(self.table, name=f"New {self.singular}")
        self.current_id = None
        self.reload()
        self.select(row_id)
        self.name.setFocus()
        self.name.selectAll()

    def delete(self):
        if self.current_id is None:
            return
        name = self.name.text() or f"this {self.singular}"
        if not confirm(self, f"Delete {self.singular}", f"Delete “{name}”? This cannot be undone."):
            return
        self.saver.timer.stop()
        self.project.delete(self.table, self.current_id)
        self.current_id = None
        self.reload()
        self.project_changed.emit()

    def move(self, delta):
        if self.current_id is None:
            return
        self.flush()
        if self.project.move(self.table, self.current_id, delta):
            self.reload()
