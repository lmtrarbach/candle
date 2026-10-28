"""The About window: what Candle is, its license, and how to support it."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from . import __version__

BIBISCO_URL = "https://bibisco.com"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

DONATIONS = (
    ("Bitcoin", "bc1qnyceh488yqr0l6ffljygf47243p8wsvct4mkw7"),
    ("Ethereum", "0x8bc6D2D3d47D15EEd881975A09F008609F3bAdF2"),
    ("Solana", "3Gq3t2Xoix8eRvyxCE8mdB5BPsNCwHxDVc8oLXMTeFe1"),
)


class AboutDialog(QDialog):
    def __init__(self, icon_path, backup_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Candle")
        self.setFixedWidth(640)

        icon = QLabel()
        icon.setPixmap(QPixmap(str(icon_path)).scaled(
            96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(f"Candle {__version__}")
        title.setObjectName("heading1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        intro = QLabel(
            "<p><b>Candle is free and open source.</b> It costs nothing, has no ads, needs no "
            "account, and your novels stay on your own computer. (Optional Candle Premium "
            "adds cloud backup for those who sign in.)</p>"
            f"<p>It is inspired by <a href='{BIBISCO_URL}'>bibisco</a>, the novel-writing "
            "software, and follows its way of working: architecture, characters, locations, "
            "strands, chapters and scenes.</p>"
            f"<p>Released under the <a href='{LICENSE_URL}'>GNU General Public License v3.0</a>: "
            "you may use, study, share and improve it.</p>"
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)

        support = QLabel(
            "<b>Support Candle</b><br>If Candle helps you write, you can support its "
            "development with a donation to one of these addresses:"
        )
        support.setWordWrap(True)

        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        grid = QGridLayout()
        for row, (coin, address) in enumerate(DONATIONS):
            field = QLineEdit(address)
            field.setReadOnly(True)
            field.setFont(mono)
            field.setCursorPosition(0)
            copy = QPushButton("Copy")
            copy.clicked.connect(lambda _=False, a=address, b=copy: self._copy(a, b))
            grid.addWidget(QLabel(coin), row, 0)
            grid.addWidget(field, row, 1)
            grid.addWidget(copy, row, 2)

        box = QFrame()
        box.setObjectName("card")
        bv = QVBoxLayout(box)
        bv.addWidget(support)
        bv.addLayout(grid)
        thanks = QLabel("Thank you ♥")
        thanks.setObjectName("hint")
        bv.addWidget(thanks)

        files = QLabel(
            "Each project is a single <code>.candle</code> file (SQLite), saved as you type. "
            f"A backup is made every time you open a project, in<br><code>{backup_dir}</code>"
        )
        files.setObjectName("hint")
        files.setWordWrap(True)
        files.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(box)
        layout.addWidget(files)
        layout.addWidget(buttons)
        # Wrapped labels only know their height once the width is known.
        self.setMinimumHeight(layout.totalHeightForWidth(self.width()))

    def _copy(self, address, button):
        QGuiApplication.clipboard().setText(address)
        button.setText("Copied ✓")
        QTimer.singleShot(1500, lambda: button.setText("Copy"))
