"""Candle Premium windows: sign in, account status, and restoring cloud backups."""

import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QLabel, QMessageBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from . import cloud
from .widgets import hbox

PRIVACY_NOTE = (
    "Signing in is optional. With Candle Premium, copies of your projects are "
    "uploaded to a private folder on Candle's cloud storage (Google Cloud) that "
    "only your account can open. Without an account, Candle never goes online."
)

_running = set()


class _Task(QObject):
    finished = Signal(bool, object)

    def __init__(self, on_done, on_failed):
        super().__init__()
        self.on_done, self.on_failed = on_done, on_failed
        # Queued: the callbacks run on the UI thread, not the worker's.
        self.finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    @Slot(bool, object)
    def _deliver(self, ok, value):
        _running.discard(self)
        callback = self.on_done if ok else self.on_failed
        if callback:
            callback(value)


def run_async(fn, on_done=None, on_failed=None):
    """Run the blocking `fn` on a worker thread; call back on the UI thread."""
    task = _Task(on_done, on_failed)
    _running.add(task)

    def work():
        try:
            result = fn()
        except Exception as exc:
            task.finished.emit(False, exc)
        else:
            task.finished.emit(True, result)

    QThreadPool.globalInstance().start(work)


def open_billing(get_url, button, status):
    """Fetch a Stripe page made for this account (checkout or portal) and open it."""
    button.setEnabled(False)

    def opened(url):
        button.setEnabled(True)
        QDesktopServices.openUrl(QUrl(url))
        status.setText("Continue in your browser. When you're done, close and reopen this "
                       "window to see the change.")

    def failed(exc):
        button.setEnabled(True)
        status.setText(str(exc))

    run_async(get_url, opened, failed)


def human_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "bytes" else f"{n:,.1f} {unit}"
        n /= 1024


def local_time(iso):
    return datetime.datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")


class SignInDialog(QDialog):
    """Sign in or create an account in the browser: Google, or email and password."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Candle Premium")
        self.setFixedWidth(460)
        self.session = None
        self.flow = None

        heading = QLabel("Sign in to Candle")
        heading.setObjectName("heading1")
        note = QLabel(PRIVACY_NOTE)
        note.setObjectName("hint")
        note.setWordWrap(True)
        self.status = QLabel("Your browser opens so you can sign in with Google or your email, "
                             "or create an account.")
        self.status.setWordWrap(True)
        self.copy_link = QLabel("<a href='#'>Browser didn't open? Copy the link</a>")
        self.copy_link.linkActivated.connect(self._copy_link)
        self.copy_link.setVisible(False)

        self.go_btn = QPushButton("Continue in browser")
        self.go_btn.setObjectName("primary")
        self.go_btn.setDefault(True)
        self.go_btn.clicked.connect(self._start)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addSpacing(8)
        layout.addWidget(self.status)
        layout.addWidget(self.copy_link)
        layout.addWidget(hbox(None, cancel, self.go_btn))

    def _start(self):
        if self.flow:
            self.flow.cancel()   # a second click starts over with a new link
        flow = self.flow = cloud.BrowserSignIn()
        self.go_btn.setText("Open the browser again")
        self.copy_link.setVisible(True)
        if QDesktopServices.openUrl(QUrl(flow.url)):
            self.status.setText("Finish signing in in your browser. This window updates by itself.")
        else:
            self.status.setText("Couldn't open your browser. Copy the link below into it.")

        def done(session):
            if flow is self.flow:
                self.session = session
                self.accept()

        def failed(exc):
            if flow is self.flow and not flow._cancelled.is_set():
                self.status.setText(str(exc))
                self.go_btn.setText("Continue in browser")

        run_async(flow.wait, done, failed)

    def _copy_link(self):
        if self.flow:
            QGuiApplication.clipboard().setText(self.flow.url)
            self.status.setText("Link copied. Paste it into your browser's address bar.")

    def done(self, result):
        if self.flow and result != QDialog.DialogCode.Accepted:
            self.flow.cancel()
        super().done(result)


class AccountDialog(QDialog):
    """Status of the signed-in account, with sign out and delete."""

    signed_out = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Your account")
        self.setFixedWidth(480)

        heading = QLabel(session.email)
        heading.setObjectName("heading1")
        self.status = QLabel("Checking your account…")
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        self.resend_btn = QPushButton("Resend confirmation email")
        self.resend_btn.setVisible(False)
        self.resend_btn.clicked.connect(self._resend)
        self.premium_btn = QPushButton("See Candle Premium…")
        self.premium_btn.setObjectName("primary")
        self.premium_btn.setVisible(False)
        self.premium_btn.clicked.connect(lambda: PremiumDialog(self.session, self).exec())
        self.manage_btn = QPushButton("Manage subscription…")
        self.manage_btn.setVisible(False)
        self.manage_btn.clicked.connect(
            lambda: open_billing(self.session.billing_portal_url, self.manage_btn, self.status))
        sign_out = QPushButton("Sign out")
        sign_out.clicked.connect(self._sign_out)
        delete = QPushButton("Delete account…")
        delete.clicked.connect(self._delete)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self.status)
        layout.addWidget(self.resend_btn)
        layout.addWidget(hbox(self.premium_btn, self.manage_btn, None))
        layout.addSpacing(8)
        layout.addWidget(hbox(sign_out, delete, None))
        layout.addWidget(buttons)
        run_async(session.me, self._show, lambda exc: self.status.setText(str(exc)))

    def _show(self, me):
        if not me["email_verified"]:
            self.status.setText("Your email address isn't confirmed yet. Open the link we emailed "
                                "you, then reopen this window.")
            self.resend_btn.setVisible(True)
        elif not me["premium"]:
            self.status.setText("Free account. Cloud backup comes with <b>Candle Premium</b>.")
        else:
            limits = me["limits"]
            self.status.setText(
                f"<b>Candle Premium</b> ✓<br>{me['projects']} of {limits['projects']} projects backed up, "
                f"{human_size(me['bytes'])} in total. The latest {limits['backups_per_project']} "
                "backups of each project are kept.")
        self.premium_btn.setVisible(me["email_verified"] and me.get("can_subscribe", False))
        self.manage_btn.setVisible(me.get("can_manage_subscription", False))

    def _resend(self):
        self.resend_btn.setEnabled(False)
        run_async(self.session.send_verification,
                  lambda _: self.status.setText("Sent. Check your inbox (and spam folder)."),
                  lambda exc: self.status.setText(str(exc)))

    def _sign_out(self):
        self.signed_out.emit()
        self.accept()

    def _delete(self):
        answer = QMessageBox.warning(
            self, "Delete account",
            "Delete your Candle account and <b>every cloud backup</b> of your projects?<br><br>"
            "The .candle files on this computer are not touched. This can't be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status.setText("Deleting…")
        run_async(self.session.delete_account, lambda _: self._sign_out(),
                  lambda exc: self.status.setText(str(exc)))


class PremiumDialog(QDialog):
    """What Candle Premium is, what it costs, and the way to get or manage it."""

    FEATURES = [
        ("☁", "Cloud backup",
         "Each project is backed up when you open it and every hour while you write. The latest "
         "{keep} versions of each are kept, and you can restore any of them."),
        ("📖", "Print-ready Amazon KDP paperbacks",
         "Export a PDF interior in any of KDP's 16 trim sizes, with the margins KDP requires and "
         "chapters opening on right-hand pages."),
        ("🔒", "Private",
         "Your backups sit in a folder only your account can open. Cancel anytime: your backups "
         "stay downloadable after Premium ends."),
    ]

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.wants_sign_in = False
        self.plan_buttons = []
        self.setWindowTitle("Candle Premium")
        self.setFixedWidth(500)

        heading = QLabel("Candle Premium")
        heading.setObjectName("heading1")
        intro = QLabel("Candle stays free. Premium adds:")
        intro.setObjectName("hint")
        self.features = QLabel(self._features_html(20))
        self.features.setWordWrap(True)
        self.status = QLabel("Loading prices…")
        self.status.setWordWrap(True)
        self.manage_btn = QPushButton("Manage subscription…")
        self.manage_btn.setVisible(False)
        self.manage_btn.clicked.connect(
            lambda: open_billing(self.session.billing_portal_url, self.manage_btn, self.status))
        self.sign_in_btn = QPushButton("Sign in to get Premium")
        self.sign_in_btn.setObjectName("primary")
        self.sign_in_btn.setVisible(False)
        self.sign_in_btn.clicked.connect(self._sign_in)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(intro)
        layout.addWidget(self.features)
        layout.addSpacing(4)
        layout.addWidget(self.status)
        self.button_row = hbox(self.sign_in_btn, self.manage_btn, None, close)
        layout.addWidget(self.button_row)

        failed = lambda exc: self.status.setText(str(exc))   # noqa: E731
        if session is None:
            run_async(cloud.plans, self._show_offer, failed)
        else:
            run_async(session.me, self._show_account, failed)

    def _features_html(self, keep):
        rows = "".join(f"<tr><td style='padding:6px 10px 6px 0; font-size:18px'>{icon}</td>"
                       f"<td style='padding:6px 0'><b>{title}</b><br>{text.format(keep=keep)}</td></tr>"
                       for icon, title, text in self.FEATURES)
        return f"<table>{rows}</table>"

    @staticmethod
    def _prices(plans):
        labels = [p["label"] for p in sorted(plans, key=lambda p: p["plan"] != "yearly")]
        return " or ".join(labels)

    def _show_offer(self, offer):
        """Signed out: what it costs, and a way in."""
        self.features.setText(self._features_html(offer["backups_per_project"]))
        if not offer["plans"]:
            self.status.setText("Candle Premium isn't on sale yet.")
            return
        self.status.setText(f"<b>{self._prices(offer['plans'])}</b>. Sign in or create a free "
                            "account first; it takes a minute in your browser.")
        self.sign_in_btn.setVisible(True)

    def _show_account(self, me):
        self.features.setText(self._features_html(me["limits"]["backups_per_project"]))
        if me["premium"]:
            self.status.setText("<b>You have Candle Premium ✓</b> Thank you for supporting Candle.")
        elif not me["email_verified"]:
            self.status.setText("Confirm your email address first: open the link we emailed you, "
                                "then reopen this window.")
        elif me.get("plans"):
            self.status.setText(f"<b>{self._prices(me['plans'])}</b>. Pay securely with Stripe; "
                                "cancel anytime.")
            self._offer(me["plans"])
        else:
            self.status.setText("Candle Premium isn't on sale yet.")
        self.manage_btn.setVisible(me.get("can_manage_subscription", False))

    def _offer(self, plans):
        # Yearly first and highlighted: it's the better deal.
        for plan in sorted(plans, key=lambda p: p["plan"] != "yearly"):
            button = QPushButton(plan["label"])
            if plan["plan"] == "yearly":
                button.setObjectName("primary")
            button.clicked.connect(lambda _=False, name=plan["plan"], b=button: open_billing(
                lambda: self.session.checkout_url(name), b, self.status))
            self.button_row.layout().insertWidget(len(self.plan_buttons), button)
            self.plan_buttons.append(button)

    def _sign_in(self):
        self.wants_sign_in = True
        self.accept()


class RestoreDialog(QDialog):
    """Browse cloud backups and save one as a new .candle file."""

    def __init__(self, session, default_dir, parent=None):
        super().__init__(parent)
        self.session = session
        self.default_dir = Path(default_dir)
        self.restored_path = None
        self.setWindowTitle("Restore from cloud")
        self.resize(620, 440)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Project / backup", "Size"])
        self.tree.setColumnWidth(0, 420)
        self.tree.itemExpanded.connect(self._load_backups)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self._restore())
        self.status = QLabel("Loading…")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        self.restore_btn = QPushButton("Restore…")
        self.restore_btn.setObjectName("primary")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self._restore)
        self.delete_btn = QPushButton("Delete from cloud…")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_project)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.status)
        layout.addWidget(hbox(self.delete_btn, None, close, self.restore_btn))
        self._reload()

    def _reload(self):
        self.tree.clear()
        run_async(self.session.projects, self._show_projects, lambda exc: self.status.setText(str(exc)))

    def _show_projects(self, projects):
        for p in projects:
            item = QTreeWidgetItem([
                f"{p['title'] or 'Untitled'}   ·   {p['backups']} backups, latest {local_time(p['latest'])}",
                human_size(p["bytes"]),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, ("project", p))
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            self.tree.addTopLevelItem(item)
        self.status.setText("Pick a backup to restore. It is saved as a new file; your "
                            "current files are never overwritten." if projects
                            else "No cloud backups yet.")

    def _load_backups(self, item):
        kind, project = item.data(0, Qt.ItemDataRole.UserRole)
        if item.childCount():
            return

        def show(backups):
            for b in backups:
                child = QTreeWidgetItem([local_time(b["created"]), human_size(b["size"])])
                child.setData(0, Qt.ItemDataRole.UserRole, ("backup", {**b, "project": project}))
                item.addChild(child)

        run_async(lambda: self.session.backups(project["project_id"]), show,
                  lambda exc: self.status.setText(str(exc)))

    def _selected(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else (None, None)

    def _selection_changed(self, *_):
        kind, _ = self._selected()
        self.restore_btn.setEnabled(kind == "backup")
        self.delete_btn.setEnabled(kind == "project")

    def _restore(self):
        kind, backup = self._selected()
        if kind != "backup":
            return
        project = backup["project"]
        title = "".join(c for c in (project["title"] or "Restored") if c not in '/\\:*?"<>|')
        stamp = local_time(backup["created"]).replace(":", "")
        suggested = self.default_dir / f"{title} (restored {stamp}).candle"
        path, _ = QFileDialog.getSaveFileName(self, "Save restored project as", str(suggested),
                                              "Candle projects (*.candle)")
        if not path:
            return
        if not path.endswith(".candle"):
            path += ".candle"
        if Path(path).exists():
            QMessageBox.warning(self, "File exists", "Choose a new file name: restoring never overwrites a file.")
            return
        self.status.setText("Downloading…")
        self.restore_btn.setEnabled(False)

        def done(_):
            self.restored_path = path
            self.accept()

        def failed(exc):
            self.status.setText(str(exc))
            self.restore_btn.setEnabled(True)

        run_async(lambda: self.session.download(project["project_id"], backup["backup_id"], path), done, failed)

    def _delete_project(self):
        kind, project = self._selected()
        if kind != "project":
            return
        answer = QMessageBox.warning(
            self, "Delete from cloud",
            f"Delete all cloud backups of <b>{project['title'] or 'Untitled'}</b>?<br><br>"
            "Files on this computer are not touched.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            run_async(lambda: self.session.delete_project(project["project_id"]),
                      lambda _: self._reload(), lambda exc: self.status.setText(str(exc)))
