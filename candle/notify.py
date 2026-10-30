"""Desktop notifications, for Wick's reminders (see coach.py)."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon

ICON = Path(__file__).parent / "resources" / "candle.png"
_tray = None


def notify(title, body):
    """Show a system notification; False if this desktop can't."""
    if sys.platform.startswith("linux") and _freedesktop(title, body):
        return True
    global _tray
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return False
    if _tray is None:
        _tray = QSystemTrayIcon(QIcon(str(ICON)))
    _tray.show()
    _tray.showMessage(title, body, QIcon(str(ICON)), 15_000)
    return True


def _freedesktop(title, body):
    # The desktop portal: GNOME, KDE and the rest, inside the snap or not, no tray icon needed.
    try:
        from PySide6.QtDBus import QDBus, QDBusConnection, QDBusInterface
    except ImportError:
        return False
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    portal = QDBusInterface("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                            "org.freedesktop.portal.Notification", bus)
    if not portal.isValid():
        return False
    reply = portal.call(QDBus.CallMode.Block, "AddNotification", "wick", {"title": title, "body": body})
    return not reply.errorName()
