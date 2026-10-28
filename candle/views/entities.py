from PySide6.QtWidgets import (
    QComboBox, QLabel, QPlainTextEdit, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from ..questions import CHARACTER_SECTIONS
from ..widgets import RichEditor
from .base import EntityView


class LocationsView(EntityView):
    table = "locations"
    singular = "location"
    plural = "Locations"
    intro = "The places where your story happens."
    extra_fields = (
        ("nation", "Nation", "e.g. France"),
        ("state", "Region / state", "e.g. Provence"),
        ("city", "City", "e.g. Marseille"),
    )

    def label(self, row):
        where = ", ".join(x for x in (row["city"], row["nation"]) if x)
        name = row["name"] or "(unnamed)"
        return f"{name} — {where}" if where else name


class ObjectsView(EntityView):
    table = "objects"
    singular = "object"
    plural = "Objects"
    intro = "Items that matter to the plot: a letter, a weapon, a ring."


class StrandsView(EntityView):
    table = "strands"
    singular = "strand"
    plural = "Narrative strands"
    intro = "Plot lines and subplots woven through the scenes."


class CharactersView(EntityView):
    table = "characters"
    singular = "character"
    plural = "Characters"
    intro = "★ main characters get an in-depth interview; secondary ones a description."

    def build_extra(self, form):
        self.role = QComboBox()
        self.role.addItem("Main character", "main")
        self.role.addItem("Secondary character", "secondary")
        self.role.activated.connect(self._role_changed)
        form.addRow("Role", self.role)

    def build_body(self):
        self.tabs = QTabWidget()
        self.description = RichEditor("Who is this character? Appearance, personality, role in the story…")
        self.description.changed.connect(self.saver.poke)
        self.tabs.addTab(self.description, "Overview")

        self.answers = {}
        for key, title, questions in CHARACTER_SECTIONS:
            page = QWidget()
            pv = QVBoxLayout(page)
            for idx, question in enumerate(questions):
                label = QLabel(question)
                label.setWordWrap(True)
                label.setObjectName("question")
                answer = QPlainTextEdit()
                answer.setObjectName("answer")
                answer.setFixedHeight(84)
                answer.textChanged.connect(self.saver.poke)
                pv.addWidget(label)
                pv.addWidget(answer)
                self.answers[(key, idx)] = answer
            pv.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, title)
        return self.tabs

    def label(self, row):
        name = row["name"] or "(unnamed)"
        return f"★ {name}" if row["role"] == "main" else f"   {name}"

    def load_extra(self, row):
        self.role.setCurrentIndex(0 if row["role"] == "main" else 1)
        saved = self.project.answers(row["id"])
        for key, edit in self.answers.items():
            edit.blockSignals(True)
            edit.setPlainText(saved.get(key, ""))
            edit.blockSignals(False)
        self._show_interview(row["role"] == "main")

    def save_extra(self):
        for (section, idx), edit in self.answers.items():
            self.project.set_answer(self.current_id, section, idx, edit.toPlainText())
        return {"role": self.role.currentData()}

    def _role_changed(self):
        self._show_interview(self.role.currentData() == "main")
        self.saver.poke()
        self.saver.flush()

    def _show_interview(self, on):
        for i in range(1, self.tabs.count()):
            self.tabs.setTabVisible(i, on)
        if not on:
            self.tabs.setCurrentIndex(0)
