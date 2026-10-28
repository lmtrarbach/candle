"""Render candle/resources/candle.svg into the PNG, ICO and ICNS icons and the
Microsoft Store (MSIX) logos.

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


# Logo files referenced by packaging/msix/AppxManifest.xml: name -> (width, height).
MSIX_ASSETS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}


def msix_assets(big):
    os.makedirs("packaging/msix/Assets", exist_ok=True)
    for name, (w, h) in MSIX_ASSETS.items():
        side = min(w, h)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        icon = big.resize((side, side), Image.Resampling.LANCZOS)
        canvas.paste(icon, ((w - side) // 2, (h - side) // 2), icon)
        canvas.save(f"packaging/msix/Assets/{name}")


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
        msix_assets(big)


if __name__ == "__main__":
    main()
