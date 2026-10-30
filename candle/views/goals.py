"""Goals (Candle Premium): Wick, the writing companion, and the writer's goals."""

import datetime
import math

from PySide6.QtCore import QDate, QPointF, QRectF, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFormLayout, QFrame, QGridLayout, QLabel, QProgressBar, QPushButton,
    QSpinBox, QTimeEdit, QVBoxLayout, QWidget,
)

from .. import coach
from ..widgets import Debouncer, heading, hbox
from .base import View

FLAME = {"proud": ("#f2a33a", "#ffd77a", 1.0), "glow": ("#e98f2e", "#ffcf6e", 0.85),
         "flicker": ("#d9732a", "#f7b45c", 0.6), "sleepy": ("#b9824c", "#e6c08a", 0.42)}


class Wick(QWidget):
    """The companion: a candle whose flame shows how the writing is going."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(96, 128)
        self.mood = "glow"
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(90)

    def set_mood(self, mood):
        self.mood = mood
        self.update()

    def _tick(self):
        if self.isVisible():
            self.phase += 0.35
            self.update()

    def paintEvent(self, event):
        outer, inner, size = FLAME.get(self.mood, FLAME["glow"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        # The candle, with a face.
        body = QRectF(30, 64, 36, 58)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f6efe2"))
        p.drawRoundedRect(body, 8, 8)
        p.setBrush(QColor("#e7dcc8"))
        p.drawRoundedRect(QRectF(30, 64, 36, 9), 5, 5)
        ink = pal.color(QPalette.ColorRole.Text) if self.mood != "sleepy" else QColor("#8d8a84")
        p.setPen(ink)
        p.setBrush(ink)
        if self.mood == "sleepy":
            p.drawLine(QPointF(39, 88), QPointF(45, 88))
            p.drawLine(QPointF(51, 88), QPointF(57, 88))
        else:
            p.drawEllipse(QPointF(42, 87), 2.4, 2.8)
            p.drawEllipse(QPointF(54, 87), 2.4, 2.8)
        mouth = QPainterPath(QPointF(43, 96))
        lift = {"proud": 6, "glow": 3, "flicker": -2, "sleepy": 0}[self.mood]
        mouth.quadTo(QPointF(48, 96 + lift), QPointF(53, 96))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(mouth)
        # The wick and its flame, swaying a little.
        p.setPen(QColor("#5a4630"))
        p.drawLine(QPointF(48, 64), QPointF(48, 57))
        sway = math.sin(self.phase) * 2.2 * size
        h = 46 * size
        for colour, scale in ((outer, 1.0), (inner, 0.55)):
            path = QPainterPath(QPointF(48, 60))
            path.cubicTo(QPointF(48 - 14 * scale * size, 60 - h * 0.25 * scale), QPointF(48 - 6 * scale, 60 - h * 0.75 * scale),
                         QPointF(48 + sway, 60 - h * scale))
            path.cubicTo(QPointF(48 + 6 * scale, 60 - h * 0.75 * scale), QPointF(48 + 14 * scale * size, 60 - h * 0.25 * scale),
                         QPointF(48, 60))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colour))
            p.drawPath(path)


class GoalsView(View):
    premium_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.premium = False
        self.saver = Debouncer(self.save)

        # Wick and what it says.
        self.wick = Wick()
        self.message = QLabel()
        self.message.setObjectName("coachMessage")
        self.message.setWordWrap(True)
        self.streak = QLabel()
        self.streak.setObjectName("cardValue")
        self.pace = QLabel()
        self.pace.setObjectName("hint")
        self.pace.setWordWrap(True)
        self.today_bar = QProgressBar()
        talk = QVBoxLayout()
        talk.addWidget(self.message)
        talk.addWidget(self.today_bar)
        talk.addWidget(self.pace)
        card = QFrame()
        card.setObjectName("card")
        row = QGridLayout(card)
        row.addWidget(self.wick, 0, 0, 2, 1)
        row.addLayout(talk, 0, 1)
        row.setColumnStretch(1, 1)

        # This week, Monday first.
        self.days = []
        week = QGridLayout()
        for i in range(7):
            name, mark = QLabel(), QLabel()
            name.setObjectName("hint")
            mark.setObjectName("weekMark")
            for w in (name, mark):
                w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            week.addWidget(name, 0, i)
            week.addWidget(mark, 1, i)
            self.days.append((name, mark))
        self.week_note = QLabel()
        self.week_note.setObjectName("hint")

        # The goals.
        self.unit = QComboBox()
        self.unit.addItem("Words", "words")
        self.unit.addItem(f"Pages ({coach.WORDS_PER_PAGE} words each)", "pages")
        self.daily = QSpinBox()
        self.daily.setRange(0, 100_000)
        self.week_days = QSpinBox()
        self.week_days.setRange(1, 7)
        self.week_days.setSuffix(" days a week")
        self.target = QSpinBox()
        self.target.setRange(0, 10_000_000)
        self.use_deadline = QCheckBox("Finish by")
        self.deadline = QDateEdit()
        self.deadline.setCalendarPopup(True)
        self.deadline.setDisplayFormat("d MMMM yyyy")
        self.remind = QCheckBox("Remind me at")
        self.remind_at = QTimeEdit()
        self.remind_at.setDisplayFormat("HH:mm")
        remind_hint = QLabel("While Candle is open, if you haven't met the day's goal yet. "
                             "Candle on the web can remind you too.")
        remind_hint.setObjectName("hint")
        remind_hint.setWordWrap(True)
        self.unit.currentIndexChanged.connect(self._unit_changed)
        for w in (self.daily, self.week_days, self.target):
            w.setGroupSeparatorShown(True)
            w.valueChanged.connect(self.saver.poke)
        self.deadline.dateChanged.connect(self.saver.poke)
        self.remind_at.timeChanged.connect(self.saver.poke)
        for box in (self.use_deadline, self.remind):
            box.toggled.connect(self._toggled)
        form = QFormLayout()
        form.addRow("Count in", self.unit)
        form.addRow("Daily goal", self.daily)
        form.addRow("Write on", self.week_days)
        form.addRow("Target length", self.target)
        form.addRow(self.use_deadline, self.deadline)
        form.addRow(self.remind, self.remind_at)
        form.addRow("", remind_hint)

        self.goals = QWidget()
        g = QVBoxLayout(self.goals)
        g.setContentsMargins(0, 0, 0, 0)
        g.addWidget(card)
        g.addSpacing(10)
        g.addWidget(hbox(QLabel("<b>This week</b>"), None, self.streak))
        g.addLayout(week)
        g.addWidget(self.week_note)
        g.addSpacing(14)
        g.addWidget(QLabel("<b>Your goals for this project</b>"))
        g.addLayout(form)

        # Without Premium: what Goals are, and where to get them.
        self.locked = QFrame()
        self.locked.setObjectName("card")
        about = QLabel("<b>Meet Wick, your writing companion.</b><br><br>"
                       "Set a daily goal in words or pages, how many days a week you write, and a deadline. "
                       "Wick keeps your streak, works out the pace you need, cheers when you get there and "
                       "reminds you when you haven't — here and in Candle on the web.<br><br>"
                       "Goals are part of <b>Candle Premium</b>.")
        about.setWordWrap(True)
        get = QPushButton("Candle Premium…")
        get.setObjectName("primary")
        get.clicked.connect(self.premium_requested)
        lv = QVBoxLayout(self.locked)
        lv.addWidget(about)
        lv.addWidget(hbox(get, None))

        inner = QWidget()
        inner.setMaximumWidth(720)
        v = QVBoxLayout(inner)
        v.addWidget(heading("Goals"))
        v.addWidget(self.goals)
        v.addWidget(self.locked)
        v.addStretch(1)
        outer = QVBoxLayout(self)
        outer.addWidget(inner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.set_premium(False)

    def set_premium(self, premium):
        self.premium = premium
        self.goals.setVisible(premium)
        self.locked.setVisible(not premium)
        if premium:
            self.wick.timer.start(90)
        else:
            self.wick.timer.stop()

    # -- loading and saving ------------------------------------------------
    def _pages(self):
        return self.unit.currentData() == "pages"

    def _show_amount(self, spin, words):
        spin.setValue(round(words / coach.WORDS_PER_PAGE) if self._pages() else words)

    def _words(self, spin):
        return spin.value() * coach.WORDS_PER_PAGE if self._pages() else spin.value()

    def _set_suffixes(self):
        pages = self._pages()
        self.daily.setSuffix(" pages / day" if pages else " words / day")
        self.daily.setSingleStep(1 if pages else 100)
        self.daily.setSpecialValueText("no daily goal")
        self.target.setSuffix(" pages" if pages else " words")
        self.target.setSingleStep(10 if pages else 1000)
        self.target.setSpecialValueText("no target")

    def _widgets(self):
        return (self.unit, self.daily, self.week_days, self.target, self.use_deadline, self.deadline,
                self.remind, self.remind_at)

    def reload(self):
        p = self.project
        goals = coach.parse_goals(p.get_meta("goals", ""))
        for w in self._widgets():
            w.blockSignals(True)
        self.unit.setCurrentIndex(self.unit.findData(goals["unit"]))
        self._set_suffixes()
        self._show_amount(self.daily, int(p.get_meta("daily_goal", 0) or 0))
        self._show_amount(self.target, int(p.get_meta("target_words", 0) or 0))
        self.week_days.setValue(goals["week_days"])
        deadline = goals["deadline"]
        self.use_deadline.setChecked(bool(deadline))
        self.deadline.setDate(QDate.fromString(deadline, "yyyy-MM-dd") if deadline
                              else QDate.currentDate().addMonths(3))
        self.remind.setChecked(bool(goals["remind_at"]))
        self.remind_at.setTime(QTime.fromString(goals["remind_at"] or "19:00", "HH:mm"))
        self.deadline.setEnabled(self.use_deadline.isChecked())
        self.remind_at.setEnabled(self.remind.isChecked())
        for w in self._widgets():
            w.blockSignals(False)
        self.refresh()

    def _unit_changed(self):
        # The same goals, shown in the other unit.
        words = {spin: (spin.value() * coach.WORDS_PER_PAGE if not self._pages() else spin.value())
                 for spin in (self.daily, self.target)}
        for spin in (self.daily, self.target):
            spin.blockSignals(True)
            if self._pages():
                spin.setValue(round(words[spin] / coach.WORDS_PER_PAGE))
            else:
                spin.setValue(words[spin])
            spin.blockSignals(False)
        self._set_suffixes()
        self.saver.poke()

    def _toggled(self):
        self.deadline.setEnabled(self.use_deadline.isChecked())
        self.remind_at.setEnabled(self.remind.isChecked())
        self.saver.poke()

    def save(self):
        p = self.project
        if p is None:
            return
        p.set_meta("daily_goal", self._words(self.daily))
        p.set_meta("target_words", self._words(self.target))
        p.set_meta("goals", coach.dump_goals({
            "unit": self.unit.currentData(), "week_days": self.week_days.value(),
            "deadline": self.deadline.date().toString("yyyy-MM-dd") if self.use_deadline.isChecked() else "",
            "remind_at": self.remind_at.time().toString("HH:mm") if self.remind.isChecked() else "",
        }))
        self.refresh()
        self.project_changed.emit()

    def flush(self):
        self.saver.flush()

    # -- Wick ----------------------------------------------------------------
    def refresh(self):
        if self.project is None or not self.premium:
            return
        s = coach.for_project(self.project)
        self.wick.set_mood(s.mood)
        self.message.setText(s.message)
        self.pace.setText(s.pace_text)
        self.pace.setVisible(bool(s.pace_text))
        bar, goal, done = self.today_bar, s.today_goal, max(s.today_words, 0)
        bar.setRange(0, goal or 1)
        bar.setValue(min(done, goal) if goal else 0)
        bar.setFormat(f"Today: {coach.amount(done, s.unit)}" + (f" of {coach.amount(goal, s.unit)}" if goal else ""))
        self.streak.setText(f"🔥 {s.streak_text}" if s.streak else "")
        today = datetime.date.today()
        for (name, mark), (day, words, met) in zip(self.days, s.week):
            name.setText(f"{day:%a}")
            name.setToolTip(f"{day:%A %d %B}: {coach.amount(max(words, 0), s.unit)}")
            mark.setToolTip(name.toolTip())
            mark.setText("🔥" if met else ("·" if day > today else "○"))
        if s.week_days < 7:
            self.week_note.setText(f"{s.week_met} of {s.week_days} writing days this week.")
        else:
            self.week_note.setText("Every day counts toward your streak. Rather rest some days? "
                                   "Set how many days a week you write.")

    def shown(self):
        self.reload()
