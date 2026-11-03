from PySide6.QtWidgets import (
    QComboBox, QLabel, QPlainTextEdit, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from ..i18n import t
from ..questions import CHARACTER_SECTIONS
from ..widgets import RichEditor
from .base import EntityView


class LocationsView(EntityView):
    table = "locations"
    plural = t("Locations")
    intro = t("The places where your story happens.")
    add_label, choose, describe = t("Add location"), t("Select a location on the left, or add a new one."), t("Describe this location…")
    new_name, this, delete_title = t("New location"), t("this location"), t("Delete location")
    extra_fields = (
        ("nation", t("Nation"), t("e.g. France")),
        ("state", t("Region / state"), t("e.g. Provence")),
        ("city", t("City"), t("e.g. Marseille")),
    )

    def label(self, row):
        where = ", ".join(x for x in (row["city"], row["nation"]) if x)
        name = row["name"] or t("(unnamed)")
        return f"{name} — {where}" if where else name


class ObjectsView(EntityView):
    table = "objects"
    plural = t("Objects")
    intro = t("Items that matter to the plot: a letter, a weapon, a ring.")
    add_label, choose, describe = t("Add object"), t("Select an object on the left, or add a new one."), t("Describe this object…")
    new_name, this, delete_title = t("New object"), t("this object"), t("Delete object")


class StrandsView(EntityView):
    table = "strands"
    plural = t("Narrative strands")
    intro = t("Plot lines and subplots woven through the scenes.")
    add_label, choose, describe = t("Add strand"), t("Select a strand on the left, or add a new one."), t("Describe this strand…")
    new_name, this, delete_title = t("New strand"), t("this strand"), t("Delete strand")


class CharactersView(EntityView):
    table = "characters"
    plural = t("Characters")
    intro = t("★ main characters get an in-depth interview; secondary ones a description.")
    add_label, choose, describe = t("Add character"), t("Select a character on the left, or add a new one."), t("Describe this character…")
    new_name, this, delete_title = t("New character"), t("this character"), t("Delete character")

    def build_extra(self, form):
        self.role = QComboBox()
        self.role.addItem(t("Main character"), "main")
        self.role.addItem(t("Secondary character"), "secondary")
        self.role.activated.connect(self._role_changed)
        form.addRow(t("Role"), self.role)

    def build_body(self):
        self.tabs = QTabWidget()
        self.description = RichEditor(t("Who is this character? Appearance, personality, role in the story…"))
        self.description.changed.connect(self.saver.poke)
        self.tabs.addTab(self.description, t("Overview"))

        self.answers = {}
        for key, title, questions in CHARACTER_SECTIONS:   # English in questions.py, shown translated
            page = QWidget()
            pv = QVBoxLayout(page)
            for idx, question in enumerate(questions):
                label = QLabel(t(question))
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
            self.tabs.addTab(scroll, t(title))
        return self.tabs

    def label(self, row):
        name = row["name"] or t("(unnamed)")
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
