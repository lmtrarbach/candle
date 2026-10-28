# PyInstaller recipe: builds Candle as a Windows .exe folder, a macOS .app,
# or a Linux folder, depending on where it runs.
#   pyinstaller packaging/candle.spec --noconfirm
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from candle import __version__  # noqa: E402

# Qt modules Candle never uses; leaving them out keeps the download small.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore",
    "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSql",
    "tkinter", "pytest",
]

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "candle" / "resources"), "candle/resources")],
    hiddenimports=["docx", "typst"],
    excludes=EXCLUDES,
)
# python-docx ships an unpacked copy of its template (it only uses default.docx).
# That copy contains "[Content_Types].xml", a name MSIX reserves, so leave it out.
a.datas = [d for d in a.datas if "default-docx-template" not in d[0]]
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Candle",
    console=False,
    icon=str(ROOT / "packaging" / ("candle.icns" if sys.platform == "darwin" else "candle.ico")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Candle")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Candle.app",
        icon=str(ROOT / "packaging" / "candle.icns"),
        bundle_identifier="io.github.lmtrarbach.candle",
        version=__version__,
        info_plist={
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Candle project",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "CFBundleTypeExtensions": ["candle"],
                "CFBundleTypeIconFile": "candle.icns",
            }],
        },
    )
