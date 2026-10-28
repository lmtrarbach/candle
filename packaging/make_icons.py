"""Render candle/resources/candle.svg into the PNG, ICO and ICNS icons.

Run from the repository root: python packaging/make_icons.py  (needs Pillow)
"""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render(renderer, size, path):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    img.save(path)


def main():
    app = QGuiApplication([])  # noqa: F841 - needed for rendering
    renderer = QSvgRenderer("candle/resources/candle.svg")
    render(renderer, 256, "candle/resources/candle.png")
    with tempfile.TemporaryDirectory() as tmp:
        big_path = os.path.join(tmp, "icon.png")
        render(renderer, 1024, big_path)
        big = Image.open(big_path)
        big.save("packaging/candle.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
        big.save("packaging/candle.icns")


if __name__ == "__main__":
    main()
