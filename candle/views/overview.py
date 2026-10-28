from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .. import cloud, export, kdp
from ..questions import ARCHITECTURE_SECTIONS
from ..widgets import Debouncer, RichEditor, heading, hbox
from .base import View
from .chapters import STATUS_LABELS
from .entities import StrandsView


class ProjectView(View):
    export_requested = Signal()
    backup_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.saver = Debouncer(self.save)
        self.title = QLineEdit()
        self.author = QLineEdit()
        self.language = QLineEdit()
        self.language.setPlaceholderText("en, pt-BR, it…")
        self.language.setMaximumWidth(120)
        self.target = QSpinBox()
        self.target.setRange(0, 10_000_000)
        self.target.setSingleStep(1000)
        self.target.setSuffix(" words")
        self.target.setSpecialValueText("no target")
        self.daily = QSpinBox()
        self.daily.setRange(0, 100_000)
        self.daily.setSingleStep(100)
        self.daily.setSuffix(" words / day")
        self.daily.setSpecialValueText("no daily goal")
        for w in (self.title, self.author, self.language):
            w.textEdited.connect(self.saver.poke)
        for w in (self.target, self.daily):
            w.valueChanged.connect(self.saver.poke)

        self.total_bar = QProgressBar()
        self.today_bar = QProgressBar()
        self.path = QLabel()
        self.path.setObjectName("hint")
        self.path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        export_btn = QPushButton("Export manuscript…")
        export_btn.clicked.connect(self.export_requested)
        backup_btn = QPushButton("Back up now")
        backup_btn.clicked.connect(self.backup_requested)

        form = QFormLayout()
        form.addRow("Title", self.title)
        form.addRow("Author", self.author)
        form.addRow("Language", self.language)
        form.addRow("Target length", self.target)
        form.addRow("Daily goal", self.daily)
        form.addRow("Manuscript", self.total_bar)
        form.addRow("Today", self.today_bar)

        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.addWidget(heading("Project"))
        v.addLayout(form)
        v.addSpacing(12)
        v.addWidget(hbox(export_btn, backup_btn, None))
        v.addSpacing(12)
        v.addWidget(self.path)
        v.addStretch(1)
        outer = QVBoxLayout(self)
        outer.addWidget(inner, 0, Qt.AlignmentFlag.AlignHCenter)

    def reload(self):
        p = self.project
        for w in (self.title, self.author, self.language, self.target, self.daily):
            w.blockSignals(True)
        self.title.setText(p.get_meta("title", ""))
        self.author.setText(p.get_meta("author", ""))
        self.language.setText(p.get_meta("language", ""))
        self.target.setValue(int(p.get_meta("target_words", 0) or 0))
        self.daily.setValue(int(p.get_meta("daily_goal", 0) or 0))
        for w in (self.title, self.author, self.language, self.target, self.daily):
            w.blockSignals(False)
        self.path.setText(f"Saved automatically to {p.path}")
        self.update_progress()

    def update_progress(self):
        p = self.project
        total, today = p.total_words(), p.words_today()
        target = int(p.get_meta("target_words", 0) or 0)
        goal = int(p.get_meta("daily_goal", 0) or 0)
        _progress(self.total_bar, total, target)
        _progress(self.today_bar, max(today, 0), goal)

    def save(self):
        p = self.project
        p.set_meta("title", self.title.text())
        p.set_meta("author", self.author.text())
        p.set_meta("language", self.language.text().strip())
        p.set_meta("target_words", self.target.value())
        p.set_meta("daily_goal", self.daily.value())
        self.update_progress()
        self.project_changed.emit()

    def flush(self):
        self.saver.flush()


def _progress(bar, value, goal):
    if goal:
        bar.setRange(0, goal)
        bar.setValue(min(value, goal))
        bar.setFormat(f"{value:,} / {goal:,} words  (%p%)")
    else:
        bar.setRange(0, 1)
        bar.setValue(0)
        bar.setFormat(f"{value:,} words")


class ArchitectureView(View):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.saver = Debouncer(self.save)
        self.tabs = QTabWidget()
        self.editors = {}
        for key, title, prompt in ARCHITECTURE_SECTIONS:
            editor = RichEditor(prompt)
            editor.changed.connect(self.saver.poke)
            page = QWidget()
            pv = QVBoxLayout(page)
            hint = QLabel(prompt)
            hint.setWordWrap(True)
            hint.setObjectName("hint")
            pv.addWidget(hint)
            pv.addWidget(editor, 1)
            self.tabs.addTab(page, title)
            self.editors[key] = editor
        self.strands = StrandsView()
        self.tabs.addTab(self.strands, "Narrative strands")

        layout = QVBoxLayout(self)
        layout.addWidget(heading("Architecture"))
        layout.addWidget(self.tabs, 1)

    def set_project(self, project):
        super().set_project(project)
        self.strands.set_project(project)

    def reload(self):
        self.flush()
        for key, editor in self.editors.items():
            editor.set_html(self.project.get_meta(f"arch_{key}", ""))

    def shown(self):
        pass

    def save(self):
        for key, editor in self.editors.items():
            self.project.set_meta(f"arch_{key}", editor.html())

    def flush(self):
        self.saver.flush()
        self.strands.flush()


def time_sort_key(text):
    """Scenes with a time come first, sorted as text (so ISO-style dates order
    correctly); scenes without a time go to the end."""
    return (0, text) if text else (1, "")


class TimelineView(View):
    scene_requested = Signal(int)

    COLUMNS = ("When", "#", "Chapter", "Scene", "Point of view", "Location", "Status")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._open)

        self.order = QComboBox()
        self.order.addItem("Story time (when it happens)", "time")
        self.order.addItem("Reading order (how it is told)", "reading")
        self.order.activated.connect(self.reload)

        hint = QLabel("Give each scene a time in its Details panel (YYYY-MM-DD HH:MM sorts best). "
                      "Double-click a row to open the scene.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(heading("Timeline"))
        layout.addWidget(hint)
        layout.addWidget(hbox(QLabel("Order by"), self.order, None))
        layout.addWidget(self.table, 1)

    def reload(self):
        p = self.project
        names = {c["id"]: c["name"] for c in p.list("characters")}
        places = {loc["id"]: loc["name"] for loc in p.list("locations")}
        scenes = list(enumerate(p.all_scenes(), start=1))
        if self.order.currentData() == "time":
            scenes.sort(key=lambda pair: (time_sort_key(pair[1]["scene_time"]), pair[0]))
        chapter_numbers = {c["id"]: n for n, c in enumerate(p.list("chapters"), start=1)}

        self.table.setRowCount(len(scenes))
        for row, (number, sc) in enumerate(scenes):
            values = (
                sc["scene_time"] or "—",
                str(number),
                f"{chapter_numbers[sc['chapter_id']]}. {sc['chapter_title']}",
                sc["title"] or "Untitled scene",
                names.get(sc["pov_id"], ""),
                places.get(sc["location_id"], ""),
                STATUS_LABELS.get(sc["status"], ""),
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, sc["id"])
                self.table.setItem(row, col, item)

    def _open(self, row, _col):
        self.scene_requested.emit(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))


class StatCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        v = QVBoxLayout(self)
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        caption = QLabel(title)
        caption.setObjectName("hint")
        v.addWidget(self.value)
        v.addWidget(caption)


class AnalysisView(View):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {k: StatCard(t) for k, t in (
            ("words", "words in the manuscript"), ("today", "words written today"),
            ("chapters", "chapters"), ("scenes", "scenes"), ("done", "scenes done"),
            ("avg", "average words per scene"),
        )}
        grid = QGridLayout()
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, 0, i)

        self.chapters = QTableWidget()
        self.characters = QTableWidget()
        self.locations = QTableWidget()
        self.strands = QTableWidget()
        tabs = QTabWidget()
        tabs.addTab(self.chapters, "Chapter lengths")
        tabs.addTab(self.characters, "Characters by chapter")
        tabs.addTab(self.locations, "Locations by chapter")
        tabs.addTab(self.strands, "Strands by chapter")
        for t in (self.chapters, self.characters, self.locations, self.strands):
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        layout = QVBoxLayout(self)
        layout.addWidget(heading("Analysis"))
        layout.addLayout(grid)
        layout.addWidget(tabs, 1)

    def reload(self):
        p = self.project
        scenes = p.all_scenes()
        chapters = p.list("chapters")
        total = sum(s["words"] for s in scenes)
        done = sum(1 for s in scenes if s["status"] == "done")
        self.cards["words"].value.setText(f"{total:,}")
        self.cards["today"].value.setText(f"{p.words_today():,}")
        self.cards["chapters"].value.setText(str(len(chapters)))
        self.cards["scenes"].value.setText(str(len(scenes)))
        self.cards["done"].value.setText(f"{done} / {len(scenes)}")
        self.cards["avg"].value.setText(f"{total // len(scenes):,}" if scenes else "0")

        self._chapter_lengths(chapters, scenes)
        chapter_of = {s["id"]: s["chapter_id"] for s in scenes}

        presence = {}
        for link in p.all_links("character"):
            presence.setdefault(link["target_id"], {}).setdefault(chapter_of[link["scene_id"]], set()).add(link["scene_id"])
        for s in scenes:
            if s["pov_id"]:
                presence.setdefault(s["pov_id"], {}).setdefault(s["chapter_id"], set()).add(s["id"])
        self._matrix(self.characters, p.list("characters"), chapters, presence)

        presence = {}
        for s in scenes:
            if s["location_id"]:
                presence.setdefault(s["location_id"], {}).setdefault(s["chapter_id"], set()).add(s["id"])
        self._matrix(self.locations, p.list("locations"), chapters, presence)

        presence = {}
        for link in p.all_links("strand"):
            presence.setdefault(link["target_id"], {}).setdefault(chapter_of[link["scene_id"]], set()).add(link["scene_id"])
        self._matrix(self.strands, p.list("strands"), chapters, presence)

    def _chapter_lengths(self, chapters, scenes):
        words = {c["id"]: 0 for c in chapters}
        counts = {c["id"]: 0 for c in chapters}
        for s in scenes:
            words[s["chapter_id"]] += s["words"]
            counts[s["chapter_id"]] += 1
        longest = max(words.values(), default=0) or 1
        t = self.chapters
        t.clear()
        t.setColumnCount(4)
        t.setHorizontalHeaderLabels(["Chapter", "Scenes", "Words", ""])
        t.setRowCount(len(chapters))
        t.verticalHeader().hide()
        for row, c in enumerate(chapters):
            t.setItem(row, 0, QTableWidgetItem(f"{row + 1}. {c['title']}"))
            t.setItem(row, 1, QTableWidgetItem(str(counts[c["id"]])))
            t.setItem(row, 2, QTableWidgetItem(f"{words[c['id']]:,}"))
            bar = QProgressBar()
            bar.setRange(0, longest)
            bar.setValue(words[c["id"]])
            bar.setTextVisible(False)
            bar.setMaximumHeight(14)
            t.setCellWidget(row, 3, bar)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _matrix(self, table, entities, chapters, presence):
        table.clear()
        table.setRowCount(len(entities))
        table.setColumnCount(len(chapters) + 1)
        table.setHorizontalHeaderLabels(["Total"] + [str(n) for n in range(1, len(chapters) + 1)])
        table.setVerticalHeaderLabels([e["name"] or "(unnamed)" for e in entities])
        for col, c in enumerate(chapters, start=1):
            table.horizontalHeaderItem(col).setToolTip(c["title"])
        accent = QColor("#5b7cbf")
        for row, e in enumerate(entities):
            per_chapter = presence.get(e["id"], {})
            total = sum(len(v) for v in per_chapter.values())
            table.setItem(row, 0, QTableWidgetItem(str(total)))
            for col, c in enumerate(chapters, start=1):
                n = len(per_chapter.get(c["id"], ()))
                item = QTableWidgetItem(str(n) if n else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if n:
                    shade = QColor(accent)
                    shade.setAlpha(min(255, 70 + 50 * n))
                    item.setBackground(QBrush(shade))
                table.setItem(row, col, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)


class ExportDialog(QDialog):
    KDP_LABEL = "Amazon KDP paperback (.pdf) — Premium"

    def __init__(self, project, parent=None, session=None):
        super().__init__(parent)
        self.project = project
        self.session = session
        self.setWindowTitle("Export manuscript")
        self.format = QComboBox()
        for label, ext in export.FORMATS.items():
            self.format.addItem(label, ext)
        if cloud.configured():   # Premium only exists where the service does
            self.format.addItem(self.KDP_LABEL, "kdp")
        self.trim = QComboBox()
        self.trim.addItems(kdp.TRIM_SIZES)
        self.trim.setCurrentText(kdp.DEFAULT_TRIM)
        self.paper = QComboBox()
        self.paper.addItems(kdp.PAPERS)
        self.font_size = QSpinBox()
        self.font_size.setRange(9, 14)
        self.font_size.setValue(11)
        self.font_size.setSuffix(" pt")
        self.kdp_note = QLabel("A print-ready interior: margins and gutter sized for KDP, chapters "
                               "opening on right-hand pages, fonts embedded. No bleed.")
        self.kdp_note.setObjectName("hint")
        self.kdp_note.setWordWrap(True)
        self.title_page = QCheckBox("Title page")
        self.chapter_titles = QCheckBox("Chapter titles")
        self.number = QCheckBox("Number chapters")
        self.only_done = QCheckBox("Only scenes marked “Done”")
        for box in (self.title_page, self.chapter_titles, self.number):
            box.setChecked(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        go = buttons.addButton("Export…", QDialogButtonBox.ButtonRole.AcceptRole)
        go.setDefault(True)
        buttons.accepted.connect(self._export)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("Format", self.format)
        form.addRow("", self.title_page)
        form.addRow("", self.chapter_titles)
        form.addRow("", self.number)
        form.addRow("", self.only_done)
        self.kdp_rows = [("Trim size", self.trim), ("Paper", self.paper), ("Font size", self.font_size),
                         ("", self.kdp_note)]
        for label, widget in self.kdp_rows:
            form.addRow(label, widget)
        form.addRow(buttons)
        self.form, self.go = form, go
        self.format.currentIndexChanged.connect(self._format_changed)
        self._format_changed()

    def _format_changed(self):
        on = self.format.currentData() == "kdp"
        for _, widget in self.kdp_rows:
            self.form.setRowVisible(widget, on)
        self.adjustSize()

    def _options(self):
        return export.Options(
            chapter_titles=self.chapter_titles.isChecked(),
            number_chapters=self.number.isChecked(),
            title_page=self.title_page.isChecked(),
            only_done=self.only_done.isChecked(),
        )

    def _export(self):
        ext = self.format.currentData()
        if ext == "kdp":
            self._check_premium()
            return
        default = str(self.project.path.with_suffix(f".{ext}"))
        path, _ = QFileDialog.getSaveFileName(self, "Export manuscript", default, f"*.{ext}")
        if not path:
            return
        if not path.endswith(f".{ext}"):
            path += f".{ext}"
        options = self._options()
        try:
            export.export(self.project, path, ext, options)
        except Exception as exc:  # show any failure to the writer rather than crash
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.exported_path = path
        self.accept()

    # -- Amazon KDP (Candle Premium) ------------------------------------------
    def _check_premium(self):
        if self.session is None:
            QMessageBox.information(
                self, "Candle Premium",
                "Print-ready KDP files are part of <b>Candle Premium</b>.<br><br>"
                "Sign in under <b>Account → Sign in…</b>, then get Premium in <b>Account → Account…</b>.")
            return
        from ..account import run_async
        self.go.setEnabled(False)
        self.go.setText("Checking your account…")

        def checked(me):
            self.go.setEnabled(True)
            self.go.setText("Export…")
            if me.get("premium"):
                self._export_kdp()
            else:
                QMessageBox.information(
                    self, "Candle Premium",
                    "Print-ready KDP files are part of <b>Candle Premium</b>. "
                    "Get it in <b>Account → Account…</b>.")

        def failed(exc):
            self.go.setEnabled(True)
            self.go.setText("Export…")
            QMessageBox.warning(self, "Candle Premium", f"Couldn't check your account.\n\n{exc}")

        run_async(self.session.me, checked, failed)

    def _export_kdp(self):
        default = str(self.project.path.with_name(self.project.path.stem + " - KDP interior.pdf"))
        path, _ = QFileDialog.getSaveFileName(self, "Export KDP paperback interior", default, "*.pdf")
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"
        layout = kdp.Layout(trim=self.trim.currentText(), paper=self.paper.currentText(),
                            font_size=self.font_size.value())
        try:
            result = kdp.write_kdp_pdf(self.project, path, self._options(), layout)
        except Exception as exc:  # show any failure to the writer rather than crash
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        trim = layout.trim.split(" (")[0]
        notes = "".join(f"<br><br>⚠ {w}" for w in result.warnings)
        QMessageBox.information(
            self, "KDP interior ready",
            f"<b>{result.pages} pages</b>, {trim}, inside margin {result.inside:g} in.<br><br>"
            f"When you upload it to KDP, choose:<br>"
            f"• Trim size: <b>{trim}</b><br>• Bleed: <b>No bleed</b><br>"
            f"• Paper: <b>{layout.paper.split()[0]}</b><br><br>"
            f"Order a proof copy before publishing.{notes}")
        self.exported_path = path
        self.accept()
