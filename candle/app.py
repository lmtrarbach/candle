import datetime
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QDesktopServices, QIcon, QKeySequence, QPalette, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QStackedWidget, QStyleFactory, QVBoxLayout, QWidget,
)

from . import __version__, cloud, sync
from .about import AboutDialog
from .account import AccountDialog, PremiumDialog, RestoreDialog, SignInDialog, run_async
from .db import Project
from .views.chapters import ChaptersView
from .views.entities import CharactersView, LocationsView, ObjectsView
from .views.overview import AnalysisView, ArchitectureView, ExportDialog, ProjectView, TimelineView
from .widgets import Debouncer, hbox

APP_NAME = "Candle"
EXTENSION = ".candle"
FILE_FILTER = f"Candle projects (*{EXTENSION})"
MAX_RECENT = 8
ICON = Path(__file__).parent / "resources" / "candle.png"

THEMES = {
    "light": {
        "window": "#f3f1ec", "base": "#ffffff", "alt": "#ebe8e1", "text": "#26241f",
        "muted": "#7b766c", "accent": "#8a5a2b", "paper": "#fdfcf8", "side": "#ece9e2",
        "border": "#d6d1c6", "highlight": "#d9c3a5",
    },
    "dark": {
        "window": "#1f2023", "base": "#26272b", "alt": "#2c2d31", "text": "#e4e1da",
        "muted": "#8d8a84", "accent": "#d9a066", "paper": "#1b1c1f", "side": "#232428",
        "border": "#3a3b40", "highlight": "#5a4630",
    },
}

STYLESHEET = """
QWidget {{ font-size: 10.5pt; }}
#nav {{ background: {side}; border: none; border-right: 1px solid {border}; padding-top: 8px;
        font-size: 11pt; outline: 0; }}
#nav::item {{ padding: 10px 18px; border-left: 3px solid transparent; }}
#nav::item:selected {{ background: {window}; color: {accent}; border-left: 3px solid {accent}; }}
#sidePanel {{ background: {side}; }}
#heading1 {{ font-size: 17pt; font-weight: 600; padding: 4px 0 6px 0; }}
#hint {{ color: {muted}; }}
#question {{ font-weight: 600; margin-top: 8px; }}
#titleEdit {{ font-size: 15pt; border: none; border-bottom: 1px solid {border};
              background: transparent; padding: 4px 2px; }}
#titleEdit:focus {{ border-bottom: 2px solid {accent}; }}
#paper {{ background: {paper}; border: none; selection-background-color: {highlight};
          selection-color: {text}; font-family: "Literata", "Noto Serif", "DejaVu Serif", "Georgia",
                       "Cambria", serif;
          font-size: 13pt; }}
#editorToolbar {{ border: none; border-bottom: 1px solid {border}; spacing: 2px; padding: 2px; }}
#wordCount {{ color: {muted}; padding: 3px; border-top: 1px solid {border}; }}
#card {{ background: {base}; border: 1px solid {border}; border-radius: 8px; }}
#cardValue {{ font-size: 20pt; font-weight: 600; color: {accent}; }}
#welcomeTitle {{ font-size: 40pt; font-family: "Noto Serif", "Georgia", serif; color: {accent}; }}
#welcomeTag {{ font-size: 13pt; color: {muted}; }}
QPushButton {{ padding: 5px 12px; }}
QPushButton#primary {{ background: {accent}; color: {paper}; border: none; border-radius: 4px;
                       padding: 8px 18px; font-weight: 600; }}
QSplitter::handle {{ background: {border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
"""


def system_prefers_dark(app):
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def apply_theme(app, name):
    colors = THEMES[name]
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    roles = QPalette.ColorRole
    pal.setColor(roles.Window, QColor(colors["window"]))
    pal.setColor(roles.WindowText, QColor(colors["text"]))
    pal.setColor(roles.Base, QColor(colors["base"]))
    pal.setColor(roles.AlternateBase, QColor(colors["alt"]))
    pal.setColor(roles.Text, QColor(colors["text"]))
    pal.setColor(roles.Button, QColor(colors["alt"]))
    pal.setColor(roles.ButtonText, QColor(colors["text"]))
    pal.setColor(roles.Highlight, QColor(colors["highlight"]))
    pal.setColor(roles.HighlightedText, QColor(colors["text"]))
    pal.setColor(roles.ToolTipBase, QColor(colors["base"]))
    pal.setColor(roles.ToolTipText, QColor(colors["text"]))
    pal.setColor(roles.PlaceholderText, QColor(colors["muted"]))
    pal.setColor(roles.Link, QColor(colors["accent"]))
    for role in (roles.Text, roles.WindowText, roles.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["muted"]))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET.format(**colors))


class WelcomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        title = QLabel(APP_NAME)
        title.setObjectName("welcomeTitle")
        tag = QLabel("A quiet place to write your novel.")
        tag.setObjectName("welcomeTag")
        new = QPushButton("New project…")
        new.setObjectName("primary")
        new.clicked.connect(window.new_project)
        open_ = QPushButton("Open project…")
        open_.clicked.connect(window.open_dialog)
        self.recent = QListWidget()
        self.recent.setMaximumHeight(220)
        self.recent.itemActivated.connect(lambda item: window.open_project(item.data(Qt.ItemDataRole.UserRole)))
        self.recent_label = QLabel("Recent projects")
        self.recent_label.setObjectName("hint")

        inner = QWidget()
        inner.setFixedWidth(520)
        v = QVBoxLayout(inner)
        v.addWidget(title)
        v.addWidget(tag)
        v.addSpacing(24)
        v.addWidget(hbox(new, open_, None))
        v.addSpacing(24)
        v.addWidget(self.recent_label)
        v.addWidget(self.recent)
        v.addSpacing(24)
        free = QLabel("Candle is free and open source, inspired by bibisco. "
                      "<a href='about'>About &amp; donations</a>")
        free.setObjectName("hint")
        free.setWordWrap(True)
        free.linkActivated.connect(lambda _: window.show_about())
        v.addWidget(free)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        outer.addWidget(inner, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(2)

    def refresh(self, recent):
        self.recent.clear()
        for path in recent:
            item = QListWidgetItem(f"{Path(path).stem}    —    {path}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.recent.addItem(item)
        self.recent.setVisible(bool(recent))
        self.recent_label.setVisible(bool(recent))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.project = None
        self.session = self._load_session()
        self._cloud_busy = False
        self.focus_mode = False
        self.full_view = False
        self._was_maximized = False
        self.resize(1280, 820)

        self.welcome = WelcomePage(self)

        self.views = [
            ("Project", ProjectView()),
            ("Architecture", ArchitectureView()),
            ("Chapters", ChaptersView()),
            ("Characters", CharactersView()),
            ("Locations", LocationsView()),
            ("Objects", ObjectsView()),
            ("Timeline", TimelineView()),
            ("Analysis", AnalysisView()),
        ]
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(170)
        self.pages = QStackedWidget()
        for name, view in self.views:
            self.nav.addItem(name)
            self.pages.addWidget(view)
            view.project_changed.connect(self.update_status)
        self.nav.currentRowChanged.connect(self._navigate)

        self.project_view = self.views[0][1]
        self.chapters_view = self.views[2][1]
        self.chapters_view.full_view_requested.connect(self.toggle_full_view)
        self.project_view.export_requested.connect(self.export)
        self.project_view.backup_requested.connect(self.backup_now)
        for _, view in self.views:
            if hasattr(view, "scene_requested"):
                view.scene_requested.connect(self.goto_scene)

        workspace = QWidget()
        wl = QHBoxLayout(workspace)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self.nav)
        wl.addWidget(self.pages, 1)

        self.central = QStackedWidget()
        self.central.addWidget(self.welcome)
        self.central.addWidget(workspace)
        self.setCentralWidget(self.central)

        self.save_label = QLabel()
        self.save_label.setObjectName("hint")
        self.save_button = QPushButton("Save")
        self.save_button.setToolTip("Save now (Ctrl+S). Candle also saves automatically as you write.")
        self.save_button.clicked.connect(self.save_now)
        self.words_label = QLabel()
        for widget in (self.save_label, self.save_button, self.words_label):
            self.statusBar().addPermanentWidget(widget)
        self._saved_at = None
        self.save_watch = QTimer(self)
        self.save_watch.timeout.connect(self._update_save_state)
        self.save_watch.start(400)
        self._build_menus()
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._escape)

        # Periodic flush so nothing is lost even if the app is killed.
        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self.flush)
        self.autosave.start(30_000)

        # Candle Premium: back up to the cloud every hour while a project is open.
        self.cloud_timer = QTimer(self)
        self.cloud_timer.timeout.connect(lambda: self.cloud_backup(quiet=True))
        self.cloud_timer.start(60 * 60_000)

        self._show_welcome()

    # -- menus ------------------------------------------------------------
    def _build_menus(self):
        bar = self.menuBar()
        file = bar.addMenu("&File")
        file.addAction("&New project…", QKeySequence.StandardKey.New, self.new_project)
        file.addAction("&Open project…", QKeySequence.StandardKey.Open, self.open_dialog)
        self.recent_menu = file.addMenu("Open &recent")
        file.addSeparator()
        self.save_action = file.addAction("&Save", QKeySequence.StandardKey.Save, self.save_now)
        self.project_actions = [
            file.addAction("&Export manuscript…", QKeySequence("Ctrl+Shift+E"), self.export),
            file.addAction("&Back up now", self.backup_now),
            file.addAction("&Close project", QKeySequence("Ctrl+W"), self.close_project),
        ]
        file.addSeparator()
        file.addAction("&Quit", QKeySequence.StandardKey.Quit, self.close)

        view = bar.addMenu("&View")
        self.full_view_action = view.addAction("F&ull view", QKeySequence("Ctrl+Shift+F"), self.toggle_full_view)
        self.full_view_action.setCheckable(True)
        self.focus_action = view.addAction("&Focus mode", QKeySequence("F11"), self.toggle_focus)
        # Also attach to the window, so the shortcuts keep working while the menu bar is hidden.
        self.addActions([self.full_view_action, self.focus_action, self.save_action])
        self.project_actions += [self.full_view_action, self.focus_action, self.save_action]
        view.addSeparator()
        for i, (name, _) in enumerate(self.views):
            act = view.addAction(name, QKeySequence(f"Ctrl+{i + 1}"), lambda i=i: self.nav.setCurrentRow(i))
            self.project_actions.append(act)
        view.addSeparator()
        theme_menu = view.addMenu("&Theme")
        group = QActionGroup(self)
        current = self.settings.value("theme", "system")
        for key, label in (("system", "Follow system"), ("light", "Light"), ("dark", "Dark")):
            act = QAction(label, self, checkable=True)
            act.setChecked(key == current)
            act.triggered.connect(lambda _=False, k=key: self.set_theme(k))
            group.addAction(act)
            theme_menu.addAction(act)

        if cloud.configured():
            self.account_menu = bar.addMenu("&Account")
            self.account_menu.aboutToShow.connect(self._fill_account_menu)
            self._fill_account_menu()

        help_ = bar.addMenu("&Help")
        help_.addAction("&Keyboard shortcuts", self._shortcuts)
        help_.addAction("&Support Candle ♥", self.show_about)
        help_.addAction(f"&About {APP_NAME}", self.show_about)

    def set_theme(self, key):
        self.settings.setValue("theme", key)
        app = QApplication.instance()
        apply_theme(app, resolve_theme(app, key))

    def _refresh_recent(self):
        recent = self.recent()
        self.recent_menu.clear()
        for path in recent:
            self.recent_menu.addAction(path, lambda p=path: self.open_project(p))
        self.recent_menu.setEnabled(bool(recent))
        self.welcome.refresh(recent)

    def recent(self):
        paths = self.settings.value("recent", []) or []
        if isinstance(paths, str):
            paths = [paths]
        return [p for p in paths if Path(p).exists()][:MAX_RECENT]

    def _remember(self, path):
        paths = [str(path)] + [p for p in self.recent() if p != str(path)]
        self.settings.setValue("recent", paths[:MAX_RECENT])

    # -- project lifecycle ------------------------------------------------
    def new_project(self):
        title, ok = QInputDialog.getText(self, "New project", "Title of your novel:")
        if not ok or not title.strip():
            return
        folder = self.settings.value("last_dir", str(Path.home() / "Documents"))
        safe = "".join(c for c in title.strip() if c not in '/\\:*?"<>|')
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", str(Path(folder) / (safe + EXTENSION)), FILE_FILTER)
        if not path:
            return
        if not path.endswith(EXTENSION):
            path += EXTENSION
        if Path(path).exists():
            QMessageBox.warning(self, "File exists", "A file with that name already exists. Choose another name.")
            return
        try:
            Project.create(path, title.strip()).close()
        except Exception as exc:
            QMessageBox.critical(self, "Could not create project", str(exc))
            return
        self.open_project(path)
        self.nav.setCurrentRow(1)

    def open_dialog(self):
        folder = self.settings.value("last_dir", str(Path.home() / "Documents"))
        path, _ = QFileDialog.getOpenFileName(self, "Open project", folder, FILE_FILTER)
        if path:
            self.open_project(path)

    def open_project(self, path):
        self.close_project()
        try:
            project = Project(path)
            project.backup(self.backup_dir())
            project.start_day()
        except Exception as exc:
            QMessageBox.critical(self, "Could not open project", f"{path}\n\n{exc}")
            return
        self.project = project
        self._saved_at = None
        self.settings.setValue("last_dir", str(Path(path).parent))
        self._remember(path)
        for _, view in self.views:
            view.set_project(project)
        self.central.setCurrentIndex(1)
        for act in self.project_actions:
            act.setEnabled(True)
        self.nav.setCurrentRow(-1)
        self.nav.setCurrentRow(2)
        self.update_status()
        self._refresh_recent()
        self.cloud_sync()

    def close_project(self):
        if self.project is None:
            return
        self.leave_expanded_views()
        self.flush()
        for _, view in self.views:
            view.set_project(None)
        self.project.close()
        self.project = None
        self._show_welcome()

    def _show_welcome(self):
        self.central.setCurrentIndex(0)
        self.setWindowTitle(APP_NAME)
        self.words_label.clear()
        for act in self.project_actions:
            act.setEnabled(False)
        self._refresh_recent()

    def save_now(self):
        """Write every pending edit and make the .candle file complete on its own."""
        if self.project is None:
            return
        self.flush()
        self.project.checkpoint()
        self._saved_at = datetime.datetime.now()
        self._update_save_state()
        self.update_status()

    def _update_save_state(self):
        has_project = self.project is not None
        self.save_label.setVisible(has_project)
        self.save_button.setVisible(has_project)
        if not has_project:
            return
        if Debouncer.any_pending():
            self.save_label.setText("Saving…")
        elif self._saved_at:
            self.save_label.setText(f"Saved ✓ {self._saved_at:%H:%M}")
        else:
            self.save_label.setText("All changes saved ✓")

    def flush(self):
        if self.project is None:
            return
        for _, view in self.views:
            view.flush()

    def closeEvent(self, event):
        self.close_project()
        # Let a cloud upload that's under way finish.
        QThreadPool.globalInstance().waitForDone(15_000)
        event.accept()

    def backup_dir(self):
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(base or Path.home() / ".local/share/candle") / "backups"

    def backup_now(self):
        if self.project:
            self.flush()
            target = self.project.backup(self.backup_dir())
            self.statusBar().showMessage(f"Backup saved to {target}", 6000)

    def export(self):
        if self.project is None:
            return
        self.flush()
        dialog = ExportDialog(self.project, self, self.session)
        if dialog.exec():
            self.statusBar().showMessage(f"Exported to {dialog.exported_path}", 8000)

    # -- Candle Premium ---------------------------------------------------
    def _load_session(self):
        token = self.settings.value("cloud/refresh_token")
        if not (cloud.configured() and token):
            return None
        return cloud.Session(self.settings.value("cloud/email", ""), token)

    def _fill_account_menu(self):
        menu = self.account_menu
        menu.clear()
        if self.session is None:
            menu.addAction("&Sign in or create account…", self.sign_in)
            menu.addAction("Candle &Premium…", self.show_premium)
            menu.addAction("Open web &dashboard", self.open_dashboard)
            menu.addAction("&Write on the web", self.open_web_writer)
            return
        menu.addAction(f"Signed in as {self.session.email}").setEnabled(False)
        menu.addAction("&Back up to cloud now", self.cloud_backup).setEnabled(self.project is not None)
        menu.addAction("&Restore from cloud…", self.restore_from_cloud)
        menu.addSeparator()
        menu.addAction("Candle &Premium…", self.show_premium)
        menu.addAction("Open web &dashboard", self.open_dashboard)
        menu.addAction("&Write on the web", self.open_web_writer)
        menu.addAction("&Account…", self.show_account)
        menu.addAction("Sign &out", self.sign_out)

    def sign_in(self):
        dialog = SignInDialog(self)
        if not dialog.exec() or dialog.session is None:
            return
        self.session = dialog.session
        self.settings.setValue("cloud/email", self.session.email)
        self.settings.setValue("cloud/refresh_token", self.session.refresh_token)
        self.statusBar().showMessage(f"Signed in as {self.session.email}", 6000)
        self.cloud_backup(quiet=True)

    def sign_out(self):
        self.session = None
        self.settings.remove("cloud")

    def open_dashboard(self):
        # Every backup version to download, and KDP files, in the browser.
        QDesktopServices.openUrl(QUrl(f"{cloud.API_URL}/account"))

    def open_web_writer(self):
        # Candle on the web (Premium): this project, if one is open and backed up.
        query = f"?project={self.project.cloud_id()}" if self.project is not None else ""
        QDesktopServices.openUrl(QUrl(f"{cloud.API_URL}/{query}"))

    def show_premium(self):
        dialog = PremiumDialog(self.session, self)
        dialog.exec()
        if dialog.wants_sign_in:
            self.sign_in()
            if self.session is not None:
                self.show_premium()   # now with the buttons to buy it

    def show_account(self):
        dialog = AccountDialog(self.session, self)
        dialog.signed_out.connect(self.sign_out)
        dialog.exec()

    # -- Changes made in Candle on the web ---------------------------------
    def cloud_sync(self):
        """On opening a project: bring in changes made on the web, then back up."""
        if self.project is None or self.session is None:
            return
        project, session = self.project, self.session
        project_id = project.cloud_id()

        def checked(backups):
            if project is not self.project:
                return
            latest = backups[0] if backups else None
            if latest and latest.get("source") == "web" and latest["backup_id"] != project.get_meta("cloud_base"):
                if self._offer_web_version(project, latest):
                    return   # loading it; the project is reopened and backed up after
            self.cloud_backup(quiet=True)

        # Offline or signed out: back up as usual, which reports nothing when quiet.
        run_async(lambda: session.backups(project_id), checked, lambda exc: self.cloud_backup(quiet=True))

    def _offer_web_version(self, project, latest):
        """Ask about a newer version written on the web; True if it's being loaded."""
        when = datetime.datetime.fromisoformat(latest["created"]).astimezone().strftime("%Y-%m-%d %H:%M")
        if sync.unchanged_since_sync(project):
            answer = QMessageBox.question(
                self, "Changes made on the web",
                f"This book was edited in Candle on the web ({when}).<br><br>Bring those changes in? "
                "This file hasn't changed since its last cloud backup, so nothing here is lost; a copy "
                "of it is kept in Candle's backups first.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self._load_web_version(project, latest)
                return True
            return False
        box = QMessageBox(QMessageBox.Icon.Warning, "Edited in two places",
                          f"This book was edited in Candle on the web ({when}), and it also changed here "
                          "since then. Nothing is merged automatically.<br><br>"
                          "You can save the web version as a separate file to compare the two.", parent=self)
        save_copy = box.addButton("Save the web version as a file…", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Keep this file", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is save_copy:
            self._save_web_copy(project, latest, when)
        return False

    def _load_web_version(self, project, latest):
        folder = Path(tempfile.mkdtemp(prefix="candle-web-"))
        target = folder / "web.candle"
        project_id, path = project.cloud_id(), project.path
        self.statusBar().showMessage("Loading the changes made on the web…")

        def done(_):
            try:
                if project is self.project:
                    self.flush()
                    project.backup(self.backup_dir())   # a way back, just in case
                    sync.adopt_version(project, target)
                    sync.remember(project, latest["backup_id"], sync.fingerprint(project))
                    self.open_project(str(path))         # reload every view; backs up again
                    self.statusBar().showMessage("Loaded the changes made on the web ✓", 8000)
            finally:
                shutil.rmtree(folder, ignore_errors=True)

        def failed(exc):
            shutil.rmtree(folder, ignore_errors=True)
            QMessageBox.warning(self, "Changes made on the web", f"Couldn't load them.\n\n{exc}")
            self.cloud_backup(quiet=True)

        run_async(lambda: self.session.download(project_id, latest["backup_id"], target), done, failed)

    def _save_web_copy(self, project, latest, when):
        default = project.path.with_name(f"{project.path.stem} (web {when[:10]}).candle")
        path, _ = QFileDialog.getSaveFileName(self, "Save the web version", str(default), "Candle project (*.candle)")
        if not path:
            return
        target = Path(path if path.endswith(".candle") else path + ".candle")
        if target.exists():
            QMessageBox.warning(self, "File exists", "A file with that name already exists. Choose another name.")
            return

        def done(_):
            sync.detach(target)   # its own project from now on, with its own backups
            QMessageBox.information(self, "Web version saved",
                                    f"Saved as {target.name}. Open it with File → Open to compare; "
                                    "it's a separate project now.")

        run_async(lambda: self.session.download(project.cloud_id(), latest["backup_id"], target), done,
                  lambda exc: QMessageBox.warning(self, "Web version", f"Couldn't save it.\n\n{exc}"))

    def cloud_backup(self, quiet=False):
        if self.project is None or self.session is None or self._cloud_busy:
            return
        self.flush()
        project_id = self.project.cloud_id()   # before the snapshot, so copies keep it
        project, print_ = self.project, sync.fingerprint(self.project)
        folder = Path(tempfile.mkdtemp(prefix="candle-upload-"))
        snapshot = self.project.snapshot(folder / "project.candle")
        title, session = self.project.title, self.session
        self._cloud_busy = True
        if not quiet:
            self.statusBar().showMessage("Backing up to the cloud…")

        def upload():
            try:
                return session.upload(project_id, title, snapshot)
            finally:
                shutil.rmtree(folder, ignore_errors=True)

        def done(result):
            self._cloud_busy = False
            if project is self.project and result:
                sync.remember(project, result["backup_id"], print_)   # what this file now matches
            self.statusBar().showMessage("Backed up to the cloud ✓", 6000)

        def failed(exc):
            self._cloud_busy = False
            self._cloud_failed(exc, quiet)

        run_async(upload, done, failed)

    def _cloud_failed(self, exc, quiet):
        if getattr(exc, "session_ended", False):
            self.sign_out()
            QMessageBox.information(self, "Signed out", f"{exc}\n\nUse Account → Sign in to continue.")
        elif quiet and getattr(exc, "status", 0) in (402, 403):
            pass   # not Premium, or email not confirmed yet: Account… explains
        elif quiet:
            self.statusBar().showMessage(f"Cloud backup failed: {str(exc).splitlines()[0]}", 8000)
        else:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "Cloud backup", str(exc))

    def restore_from_cloud(self):
        folder = self.settings.value("last_dir", str(Path.home() / "Documents"))
        dialog = RestoreDialog(self.session, folder, self)
        if dialog.exec() and dialog.restored_path:
            self.open_project(dialog.restored_path)

    # -- navigation -------------------------------------------------------
    def _navigate(self, row):
        if row < 0 or self.project is None:
            return
        if self.pages.currentWidget() is self.chapters_view and self.views[row][1] is not self.chapters_view:
            self.leave_expanded_views()
        for _, view in self.views:
            view.flush()
        self.pages.setCurrentIndex(row)
        self.views[row][1].shown()

    def goto_scene(self, scene_id):
        self.nav.setCurrentRow(2)
        self.chapters_view.open_scene(scene_id)

    def update_status(self):
        if self.project is None:
            return
        p = self.project
        today = p.words_today()
        goal = int(p.get_meta("daily_goal", 0) or 0)
        today_text = f"today {today:+,}" + (f" / {goal:,}" if goal else "")
        self.words_label.setText(f"{p.total_words():,} words  ·  {today_text}  ")
        self.setWindowTitle(f"{p.title} — {APP_NAME}")

    # -- full view and focus mode -----------------------------------------
    # Full view: the scene editor fills the window (side panels hidden).
    # Focus mode: full screen, with only the text visible.
    def _can_expand(self, mode_name):
        if self.pages.currentWidget() is self.chapters_view and self.chapters_view.has_open_scene():
            return True
        self.statusBar().showMessage(f"Open a scene in Chapters to use {mode_name}.", 4000)
        return False

    def _apply_view(self):
        self.nav.setVisible(not (self.full_view or self.focus_mode))
        self.menuBar().setVisible(not self.focus_mode)
        self.statusBar().setVisible(not self.focus_mode)
        self.chapters_view.set_view(self.full_view, self.focus_mode)
        self.full_view_action.setChecked(self.full_view)
        if self.full_view or self.focus_mode:
            self.chapters_view.scene_panel.editor.edit.setFocus()

    def toggle_full_view(self):
        if self.project is None or self.focus_mode:
            return
        if not self.full_view and not self._can_expand("full view"):
            self._apply_view()   # undo the button's own check state
            return
        self.full_view = not self.full_view
        self._apply_view()

    def toggle_focus(self):
        if self.project is None:
            return
        if not self.focus_mode:
            if not self._can_expand("focus mode"):
                return
            self._was_maximized = self.isMaximized()
        self.focus_mode = not self.focus_mode
        self._apply_view()
        if self.focus_mode:
            self.showFullScreen()
        elif self._was_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def leave_expanded_views(self):
        if self.focus_mode:
            self.toggle_focus()
        if self.full_view:
            self.toggle_full_view()

    def _escape(self):
        if self.focus_mode:
            self.toggle_focus()
        elif self.full_view:
            self.toggle_full_view()

    # -- help -------------------------------------------------------------
    def _shortcuts(self):
        mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
        QMessageBox.information(self, "Keyboard shortcuts", """
<table cellpadding=3>
<tr><td><b>Ctrl+Shift+F</b></td><td>Full view: the text fills the window (Esc to leave)</td></tr>
<tr><td><b>F11</b></td><td>Focus mode: full screen, text only (Esc to leave)</td></tr>
<tr><td><b>Ctrl+1 … Ctrl+8</b></td><td>Switch section</td></tr>
<tr><td><b>Ctrl+B / I / U</b></td><td>Bold / italic / underline</td></tr>
<tr><td><b>Ctrl+Shift+X</b></td><td>Strikethrough</td></tr>
<tr><td><b>Ctrl+Shift+8 / 7</b></td><td>Bulleted / numbered list</td></tr>
<tr><td><b>Ctrl+L / E / R / J</b></td><td>Align left / center / right / justify</td></tr>
<tr><td><b>Ctrl+F</b></td><td>Find in the current text</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save now (Candle also saves automatically)</td></tr>
<tr><td><b>Ctrl+Shift+E</b></td><td>Export manuscript</td></tr>
</table>""".replace("Ctrl", mod))

    def show_about(self):
        AboutDialog(ICON, self.backup_dir(), self).exec()


def resolve_theme(app, key):
    if key == "system":
        return "dark" if system_prefers_dark(app) else "light"
    return key


def main(argv=None):
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("candle")
    app.setWindowIcon(QIcon(str(ICON)))
    settings = QSettings(APP_NAME, APP_NAME)
    apply_theme(app, resolve_theme(app, settings.value("theme", "system")))

    window = MainWindow()
    window.show()
    if len(argv) > 1 and Path(argv[1]).exists():
        window.open_project(argv[1])
    return app.exec()
