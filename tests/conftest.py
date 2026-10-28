import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Keep tests away from the user's real Candle settings, recent files and backups.
_sandbox = tempfile.mkdtemp(prefix="candle-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_sandbox, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_sandbox, "data")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
