"""Reusable widgets: the rich text editor, check lists, debounced saving."""

import weakref

from PySide6.QtCore import QMimeData, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QFont, QIcon, QKeySequence, QTextBlockFormat, QTextCharFormat,
    QTextCursor, QTextListFormat,
)
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QSizePolicy,
    QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

from . import richtext
from .db import count_words

LINE_HEIGHT = 150      # percent
TEXT_COLUMN = 760      # max width of the text column, in pixels


class Debouncer:
    """Call `callback` once things have been quiet for `ms` milliseconds."""

    _instances = weakref.WeakSet()

    def __init__(self, callback, ms=700):
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(ms)
        self.timer.timeout.connect(callback)
        self.callback = callback
        Debouncer._instances.add(self)

    @classmethod
    def any_pending(cls):
        """True while some edit is still waiting to be written."""
        return any(d.timer.isActive() for d in cls._instances)

    def poke(self):
        self.timer.start()

    def flush(self):
        if self.timer.isActive():
            self.timer.stop()
            self.callback()


class TextEdit(QTextEdit):
    """QTextEdit with a centered text column and sanitized paste."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setTabChangesFocus(False)
        self.column = TEXT_COLUMN

    def resizeEvent(self, event):
        # Margins first, so the text is laid out for the narrowed viewport.
        self.update_margins()
        super().resizeEvent(event)

    def update_margins(self):
        margin = max(0, (self.width() - self.column) // 2)
        self.setViewportMargins(margin, 0, margin, 0)

    def insertFromMimeData(self, source: QMimeData):
        if source.hasHtml():
            clean = richtext.to_html(richtext.parse(source.html()))
            self.textCursor().insertHtml(clean)
            apply_line_height(self.document())
        elif source.hasText():
            self.textCursor().insertText(source.text())


def apply_line_height(document):
    cursor = QTextCursor(document)
    cursor.select(QTextCursor.SelectionType.Document)
    fmt = QTextBlockFormat()
    fmt.setLineHeight(LINE_HEIGHT, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
    fmt.setBottomMargin(6)
    cursor.mergeBlockFormat(fmt)


class RichEditor(QWidget):
    """Formatted text editor with toolbar and word count."""

    changed = Signal()

    STYLES = ("Body text", "Heading 1", "Heading 2", "Heading 3")

    def __init__(self, placeholder="", toolbar=True, parent=None):
        super().__init__(parent)
        self.edit = TextEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setObjectName("paper")
        self.edit.document().setDocumentMargin(28)
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = QToolBar()
        self.toolbar.setObjectName("editorToolbar")
        self.toolbar.setMovable(False)
        if toolbar:
            self._build_toolbar()
            layout.addWidget(self.toolbar)
        layout.addWidget(self.edit, 1)

        self.count = QLabel()
        self.count.setObjectName("wordCount")
        self.count.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.count)

        self.edit.textChanged.connect(self._on_changed)
        self.edit.cursorPositionChanged.connect(self._sync_toolbar)
        self._update_count()

    # -- public API -------------------------------------------------------
    def html(self):
        return self.edit.toHtml() if self.edit.toPlainText().strip() else ""

    def plain(self):
        return self.edit.toPlainText()

    def words(self):
        return count_words(self.plain())

    def set_html(self, html):
        self._loading = True
        self.edit.setHtml(html or "")
        apply_line_height(self.edit.document())
        self.edit.document().clearUndoRedoStacks()
        self.edit.moveCursor(QTextCursor.MoveOperation.Start)
        self._loading = False
        self._update_count()

    def set_column_width(self, px):
        self.edit.column = px
        self.edit.update_margins()

    # -- internals --------------------------------------------------------
    def _on_changed(self):
        self._update_count()
        if not self._loading:
            self.changed.emit()

    def _update_count(self):
        text = self.plain()
        self.count.setText(f"{count_words(text):,} words · {len(text):,} characters  ")

    def _action(self, icon, fallback, tip, slot, shortcut=None, checkable=False):
        act = QAction(QIcon.fromTheme(icon), fallback, self)
        act.setToolTip(tip + (f"  ({QKeySequence(shortcut).toString()})" if shortcut else ""))
        if shortcut:
            act.setShortcut(shortcut)
            act.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        self.toolbar.addAction(act)
        self.addAction(act)
        return act

    def _build_toolbar(self):
        e = self.edit
        self._action("edit-undo", "↶", "Undo", e.undo, QKeySequence.StandardKey.Undo)
        self._action("edit-redo", "↷", "Redo", e.redo, QKeySequence.StandardKey.Redo)
        self.toolbar.addSeparator()

        self.style_box = QComboBox()
        self.style_box.addItems(self.STYLES)
        self.style_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.style_box.activated.connect(self._apply_style)
        self.toolbar.addWidget(self.style_box)
        self.toolbar.addSeparator()

        self.act_bold = self._action("format-text-bold", "B", "Bold", self._bold, QKeySequence.StandardKey.Bold, True)
        self.act_italic = self._action("format-text-italic", "I", "Italic",
                                       lambda on: e.setFontItalic(on), QKeySequence.StandardKey.Italic, True)
        self.act_underline = self._action("format-text-underline", "U", "Underline",
                                          lambda on: e.setFontUnderline(on), QKeySequence.StandardKey.Underline, True)
        self.act_strike = self._action("format-text-strikethrough", "S", "Strikethrough", self._strike, "Ctrl+Shift+X", True)
        self.toolbar.addSeparator()

        self._action("format-list-unordered", "•", "Bulleted list",
                     lambda: self._list(QTextListFormat.Style.ListDisc), "Ctrl+Shift+8")
        self._action("format-list-ordered", "1.", "Numbered list",
                     lambda: self._list(QTextListFormat.Style.ListDecimal), "Ctrl+Shift+7")
        self.toolbar.addSeparator()

        group = QActionGroup(self)
        self.align_actions = {}
        for flag, icon, text, tip, key in (
            (Qt.AlignmentFlag.AlignLeft, "format-justify-left", "⇤", "Align left", "Ctrl+L"),
            (Qt.AlignmentFlag.AlignHCenter, "format-justify-center", "↔", "Center", "Ctrl+E"),
            (Qt.AlignmentFlag.AlignRight, "format-justify-right", "⇥", "Align right", "Ctrl+R"),
            (Qt.AlignmentFlag.AlignJustify, "format-justify-fill", "☰", "Justify", "Ctrl+J"),
        ):
            act = self._action(icon, text, tip, lambda _=False, f=flag: e.setAlignment(f), key, True)
            group.addAction(act)
            self.align_actions[flag] = act
        self.toolbar.addSeparator()

        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText("Find…")
        self.find_box.setClearButtonEnabled(True)
        self.find_box.setMaximumWidth(180)
        self.find_box.returnPressed.connect(self._find_next)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.find_box)
        find = QAction(self)
        find.setShortcut(QKeySequence.StandardKey.Find)
        find.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find.triggered.connect(lambda: (self.find_box.setFocus(), self.find_box.selectAll()))
        self.addAction(find)

    def _bold(self, on):
        self.edit.setFontWeight(QFont.Weight.Bold if on else QFont.Weight.Normal)

    def _strike(self, on):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(on)
        self.edit.mergeCurrentCharFormat(fmt)

    def _list(self, style):
        cursor = self.edit.textCursor()
        current = cursor.currentList()
        if current and current.format().style() == style:
            # Toggle off: remove the block(s) from the list.
            block = cursor.block()
            current.remove(block)
            fmt = cursor.blockFormat()
            fmt.setIndent(0)
            cursor.setBlockFormat(fmt)
            return
        fmt = QTextListFormat()
        fmt.setStyle(style)
        cursor.createList(fmt)

    def _apply_style(self, index):
        cursor = self.edit.textCursor()
        cursor.beginEditBlock()
        block_fmt = cursor.blockFormat()
        block_fmt.setHeadingLevel(index)
        cursor.setBlockFormat(block_fmt)
        char_fmt = QTextCharFormat()
        sizes = {0: 0, 1: 8, 2: 5, 3: 2}
        char_fmt.setFontWeight(QFont.Weight.Bold if index else QFont.Weight.Normal)
        base = self.edit.document().defaultFont().pointSizeF()
        char_fmt.setFontPointSize(base + sizes[index])
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.mergeCharFormat(char_fmt)
        cursor.endEditBlock()
        self.edit.setFocus()

    def _sync_toolbar(self):
        if not hasattr(self, "act_bold"):
            return
        fmt = self.edit.currentCharFormat()
        self.act_bold.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self.act_italic.setChecked(fmt.fontItalic())
        self.act_underline.setChecked(fmt.fontUnderline())
        self.act_strike.setChecked(fmt.fontStrikeOut())
        align = self.edit.alignment()
        for flag, act in self.align_actions.items():
            if align & flag:
                act.setChecked(True)
                break
        else:
            self.align_actions[Qt.AlignmentFlag.AlignLeft].setChecked(True)
        level = self.edit.textCursor().blockFormat().headingLevel()
        self.style_box.setCurrentIndex(min(level, 3))

    def _find_next(self):
        needle = self.find_box.text()
        if not needle:
            return
        if not self.edit.find(needle):
            self.edit.moveCursor(QTextCursor.MoveOperation.Start)
            self.edit.find(needle)


class CheckList(QListWidget):
    """A list of checkable (id, label) items. Emits toggled(id, checked)."""

    toggled = Signal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self.itemChanged.connect(self._changed)

    def populate(self, items, checked_ids):
        self._loading = True
        self.clear()
        for item_id, label in items:
            item = QListWidgetItem(label or "(untitled)")
            item.setData(Qt.ItemDataRole.UserRole, item_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if item_id in checked_ids else Qt.CheckState.Unchecked)
            self.addItem(item)
        self._loading = False

    def _changed(self, item):
        if not self._loading:
            self.toggled.emit(item.data(Qt.ItemDataRole.UserRole),
                              item.checkState() == Qt.CheckState.Checked)


def heading(text, level=1):
    label = QLabel(text)
    label.setObjectName(f"heading{level}")
    return label


def hbox(*widgets, stretch_last=False):
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    for i, item in enumerate(widgets):
        if item is None:
            layout.addStretch(1)
        else:
            layout.addWidget(item, 1 if stretch_last and i == len(widgets) - 1 else 0)
    return w
