"""Render the optional Microsoft Store logos (poster art, box art, tile icon)
into packaging/store/logos/. Run from the repository root."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer

OUT = "packaging/store/logos"
NAME = "Candle Writer"
TAGLINE = "A quiet place to write your novel"


def canvas(w, h):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    bg = QLinearGradient(0, 0, 0, h)
    bg.setColorAt(0, QColor("#352c26"))
    bg.setColorAt(1, QColor("#16120f"))
    p.fillRect(0, 0, w, h, bg)
    return img, p


def glow(p, cx, cy, r):
    g = QRadialGradient(cx, cy, r)
    g.setColorAt(0, QColor(255, 210, 122, 70))
    g.setColorAt(1, QColor(255, 210, 122, 0))
    p.setBrush(g)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))


def text(p, rect, string, size, color, weight=QFont.Weight.Normal, italic=False):
    font = QFont("Noto Serif")
    font.setStyleHint(QFont.StyleHint.Serif)
    font.setPixelSize(size)
    font.setWeight(weight)
    font.setItalic(italic)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, string)


def main():
    app = QGuiApplication([])  # noqa: F841 - needed for rendering
    icon = QSvgRenderer("candle/resources/candle.svg")
    os.makedirs(OUT, exist_ok=True)

    # Poster art 9:16
    w, h = 1440, 2160
    img, p = canvas(w, h)
    glow(p, w / 2, 820, 760)
    icon.render(p, QRectF((w - 760) / 2, 440, 760, 760))
    text(p, QRectF(0, 1330, w, 200), NAME, 150, "#f3e6cc", QFont.Weight.DemiBold)
    text(p, QRectF(0, 1530, w, 120), TAGLINE, 64, "#c9a878", italic=True)
    p.end()
    img.save(f"{OUT}/poster-art-1440x2160.png")

    # Box art 1:1
    w = h = 2160
    img, p = canvas(w, h)
    glow(p, w / 2, 900, 820)
    icon.render(p, QRectF((w - 900) / 2, 420, 900, 900))
    text(p, QRectF(0, 1430, w, 220), NAME, 170, "#f3e6cc", QFont.Weight.DemiBold)
    text(p, QRectF(0, 1660, w, 130), TAGLINE, 72, "#c9a878", italic=True)
    p.end()
    img.save(f"{OUT}/box-art-2160x2160.png")

    # App tile icon 1:1 (small: icon only)
    img = QImage(300, 300, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    icon.render(p, QRectF(0, 0, 300, 300))
    p.end()
    img.save(f"{OUT}/tile-icon-300x300.png")


if __name__ == "__main__":
    main()
