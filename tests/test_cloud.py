import json
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest
from PySide6.QtTest import QTest

from candle import cloud
from candle.db import Project


class FakeServers:
    """Answers cloud._http calls the way Firebase, the API and Cloud Storage would."""

    def __init__(self):
        self.calls = []
        self.uploads = {}
        self.api_status = {}     # path -> forced status, once
        self.token = "id-1"
        self.me = {"email_verified": True, "premium": False, "can_subscribe": True,
                   "can_manage_subscription": False,
                   "plans": [{"plan": "monthly", "label": "US$4 / month"},
                             {"plan": "yearly", "label": "US$36 / year"}],
                   "limits": {"projects": 50, "backups_per_project": 20}}
        self.bodies = {}         # path -> last JSON body sent to the API
        self.versions = []       # what GET …/backups answers

    def __call__(self, method, url, *, json_body=None, form=None, data=None, headers=None, timeout=60):
        self.calls.append((method, url, headers or {}))
        if "accounts:signInWithPassword" in url:
            if json_body["password"] != "correct horse":
                return 400, json.dumps({"error": {"message": "INVALID_LOGIN_CREDENTIALS"}}).encode()
            return 200, json.dumps({"email": json_body["email"], "idToken": self.token,
                                    "refreshToken": "refresh-1", "expiresIn": "3600"}).encode()
        if "securetoken" in url:
            self.token = "id-2"
            return 200, json.dumps({"id_token": self.token, "refresh_token": "refresh-1",
                                    "expires_in": "3600"}).encode()
        if url.startswith("https://gcs/"):
            if method == "PUT":
                self.uploads[url] = (data, headers)
                return 200, b""
            return 200, next(iter(self.uploads.values()))[0]
        path = url.removeprefix(cloud.API_URL)
        if path == "/v1/plans":   # public
            return 200, json.dumps({"plans": self.me["plans"], "backups_per_project": 20}).encode()
        if path in self.api_status:
            return self.api_status.pop(path), json.dumps({"detail": "nope"}).encode()
        if headers.get("Authorization") != f"Bearer {self.token}":
            return 401, b'{"detail": "expired"}'
        if method == "POST" and path.endswith("/backups"):
            return 201, json.dumps({"backup_id": "B1", "upload": {
                "method": "PUT", "url": "https://gcs/obj",
                "headers": {"Content-Type": "application/octet-stream", "x-goog-meta-title": "T"}}}).encode()
        if path.endswith("/complete"):
            return 200, b'{"backup_id": "B1"}'
        if method == "GET" and path.endswith("/backups"):
            return 200, json.dumps(self.versions).encode()
        if path.endswith("/download"):
            return 200, b'{"url": "https://gcs/obj"}'
        if path == "/v1/me":
            return 200, json.dumps(self.me).encode()
        if path == "/v1/billing/checkout":
            self.bodies[path] = json_body
            return 200, b'{"url": "https://checkout.stripe.com/c/pay/1"}'
        return 200, b"[]"


@pytest.fixture
def servers(monkeypatch):
    fake = FakeServers()
    monkeypatch.setattr(cloud, "_http", fake)
    monkeypatch.setattr(cloud, "API_URL", "https://api")
    monkeypatch.setattr(cloud, "FIREBASE_API_KEY", "key")
    return fake


def signed_in():
    return cloud.Session("w@example.com", "refresh-1")


def hand_over(flow, state=None, origin="https://api", token="refresh-1"):
    """What the browser's sign-in page does: POST the session to Candle."""
    port = flow.url.split("port=")[1].split("&")[0]
    body = urllib.parse.urlencode({"state": state or flow.state, "email": "w@example.com",
                                   "refresh_token": token}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/callback", data=body,
                                     headers={"Origin": origin} if origin else {})
    try:
        return urllib.request.urlopen(request, timeout=5).status
    except urllib.error.HTTPError as exc:
        return exc.code


def later(fn, *args, **kwargs):
    result = []
    thread = threading.Thread(target=lambda: result.append(fn(*args, **kwargs)))
    thread.start()
    return thread, result


def test_browser_sign_in(servers, monkeypatch):
    monkeypatch.setattr(cloud, "_http", lambda *a, **k: (servers(*a, **k)))
    flow = cloud.BrowserSignIn()
    assert flow.url.startswith("https://api/signin#port=") and f"state={flow.state}" in flow.url
    # Only the page Candle opened (it knows the state) can sign it in.
    thread, codes = later(lambda: [hand_over(flow, state="guess" * 8),
                                   hand_over(flow, origin="https://evil.example"),
                                   hand_over(flow, origin=None)])
    session = flow.wait(timeout=10)
    thread.join()
    assert codes[0] == [400, 400, 200]
    assert session.email == "w@example.com" and session.refresh_token == "refresh-1"
    assert any("securetoken" in url for _, url, _ in servers.calls)   # checked before keeping it


def test_browser_sign_in_can_be_cancelled(servers):
    flow = cloud.BrowserSignIn()
    threading.Timer(0.3, flow.cancel).start()
    with pytest.raises(cloud.CloudError, match="cancelled"):
        flow.wait(timeout=10)


def test_sign_in_dialog(qapp, servers, monkeypatch):
    from candle import account
    opened = []
    monkeypatch.setattr(account.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    dialog = account.SignInDialog()
    dialog.go_btn.click()
    assert opened == [dialog.flow.url]
    later(hand_over, dialog.flow)
    assert wait_for(lambda: dialog.session is not None)
    assert dialog.result() == account.QDialog.DialogCode.Accepted


def test_opening_the_browser_again_keeps_the_same_link(qapp, servers, monkeypatch):
    # The writer may finish in the first tab after clicking twice: it must still reach Candle.
    from candle import account
    opened = []
    monkeypatch.setattr(account.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    dialog = account.SignInDialog()
    dialog.go_btn.click()
    first = dialog.flow
    dialog.go_btn.click()
    assert dialog.flow is first and opened == [first.url, first.url]
    later(hand_over, first)
    assert wait_for(lambda: dialog.session is not None)


def test_upload_sends_the_signed_headers(servers, tmp_path):
    project = Project.create(tmp_path / "novel.candle", "Novel")
    snapshot = project.snapshot(tmp_path / "copy.candle")
    session = signed_in()
    session.upload(project.cloud_id(), "Novel", snapshot)
    data, headers = servers.uploads["https://gcs/obj"]
    assert data.startswith(cloud.SQLITE_MAGIC)
    assert headers == {"Content-Type": "application/octet-stream", "x-goog-meta-title": "T"}
    assert servers.calls[-1][1].endswith("/backups/B1/complete")


def test_expired_token_is_refreshed_once(servers):
    session = signed_in()
    servers.token = "id-rotated-on-server"   # the next API call answers 401
    session.projects()
    assert any("securetoken" in url for _, url, _ in servers.calls)


def test_api_error_detail_is_shown(servers):
    session = signed_in()
    servers.api_status["/v1/projects"] = 402
    with pytest.raises(cloud.CloudError, match="nope") as info:
        session.projects()
    assert info.value.status == 402


def test_download_never_overwrites(servers, tmp_path):
    session = signed_in()
    servers.uploads["https://gcs/obj"] = (cloud.SQLITE_MAGIC + b"x", {})
    target = tmp_path / "restored.candle"
    session.download("p" * 32, "B1", target)
    with pytest.raises(FileExistsError):
        session.download("p" * 32, "B1", target)


def test_cloud_id_is_stable_and_travels_with_copies(tmp_path):
    project = Project.create(tmp_path / "novel.candle", "Novel")
    first = project.cloud_id()
    assert len(first) == 32 and project.cloud_id() == first
    copy = project.snapshot(tmp_path / "copy.candle")
    value = sqlite3.connect(copy).execute("SELECT value FROM meta WHERE key='cloud_id'").fetchone()[0]
    assert value == first


def test_no_account_menu_or_network_when_not_configured(qapp, monkeypatch):
    from candle.app import MainWindow
    monkeypatch.setattr(cloud, "_http", lambda *a, **k: pytest.fail("went online"))
    monkeypatch.setattr(cloud, "API_URL", "")
    window = MainWindow()
    try:
        assert "&Account" not in [a.text() for a in window.menuBar().actions()]
        assert window.session is None
    finally:
        window.close()


def test_released_build_stays_offline_until_sign_in(qapp, monkeypatch):
    # The service is built in, but nothing goes online before the writer signs in.
    from candle.app import MainWindow
    monkeypatch.setattr(cloud, "_http", lambda *a, **k: pytest.fail("went online"))
    assert cloud.configured() and cloud.API_URL == "https://app.candlewriter.com"
    window = MainWindow()
    try:
        assert "&Account" in [a.text() for a in window.menuBar().actions()]
        assert window.session is None
        QTest.qWait(100)
        opened = []
        monkeypatch.setattr("candle.app.QDesktopServices.openUrl", lambda url: opened.append(url.toString()))
        window.open_dashboard()
        window.open_web_writer()
        assert opened == [f"{cloud.API_URL}/account", f"{cloud.API_URL}/"]   # Candle on the web: the home page
    finally:
        window.close()


def test_opening_a_project_backs_it_up(qapp, servers, tmp_path):
    from candle.app import MainWindow
    path = tmp_path / "novel.candle"
    Project.create(path, "Novel").close()
    window = MainWindow()
    window.session = signed_in()
    try:
        assert "&Account" in [a.text() for a in window.menuBar().actions()]
        window.open_project(str(path))
        # First a look at the cloud for changes made on the web, then the backup.
        assert wait_for(lambda: window.statusBar().currentMessage() == "Backed up to the cloud ✓")
        assert servers.uploads["https://gcs/obj"][0].startswith(cloud.SQLITE_MAGIC)
        assert window.project.get_meta("cloud_base") == "B1"     # what this file now matches
    finally:
        window.close_project()
        window.close()


def wait_for(condition):
    for _ in range(100):
        if condition():
            return True
        QTest.qWait(20)
    return False


def test_free_account_is_pointed_to_premium(qapp, servers):
    from candle import account
    dialog = account.AccountDialog(signed_in())
    try:
        assert wait_for(lambda: not dialog.premium_btn.isHidden())
        assert dialog.manage_btn.isHidden()
    finally:
        dialog.close()


def test_premium_window_signed_out(qapp, servers):
    from candle import account
    dialog = account.PremiumDialog(None)
    try:
        assert wait_for(lambda: not dialog.sign_in_btn.isHidden())
        assert "US$36 / year or US$4 / month" in dialog.status.text()
        assert "latest 20 versions" in dialog.features.text()
        assert dialog.plan_buttons == []
        dialog.sign_in_btn.click()
        assert dialog.wants_sign_in and dialog.result() == account.QDialog.DialogCode.Accepted
    finally:
        dialog.close()


def test_get_premium_opens_this_accounts_checkout(qapp, servers, monkeypatch):
    from candle import account
    opened = []
    monkeypatch.setattr(account.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    session = signed_in()
    dialog = account.PremiumDialog(session)
    try:
        assert wait_for(lambda: dialog.plan_buttons)
        assert [b.text() for b in dialog.plan_buttons] == ["US$36 / year", "US$4 / month"]
        assert dialog.manage_btn.isHidden()
        dialog.plan_buttons[1].click()
        assert wait_for(lambda: opened)
        assert opened == ["https://checkout.stripe.com/c/pay/1"]
        assert servers.bodies["/v1/billing/checkout"] == {"plan": "monthly"}
    finally:
        dialog.close()


def test_premium_accounts_get_manage_not_buy(qapp, servers):
    from candle import account
    servers.me = {"email_verified": True, "premium": True, "can_subscribe": False,
                  "can_manage_subscription": True, "projects": 1, "bytes": 2048,
                  "limits": {"projects": 50, "backups_per_project": 20}}
    dialog = account.AccountDialog(signed_in())
    premium = account.PremiumDialog(signed_in())
    try:
        assert wait_for(lambda: not dialog.manage_btn.isHidden())
        assert dialog.premium_btn.isHidden()
        assert wait_for(lambda: not premium.manage_btn.isHidden())
        assert premium.plan_buttons == [] and "You have Candle Premium" in premium.status.text()
    finally:
        dialog.close()
        premium.close()


@pytest.fixture
def kdp_dialog(qapp, servers, tmp_path, monkeypatch):
    from candle.views import overview
    shown = []
    monkeypatch.setattr(overview.QMessageBox, "information", lambda parent, title, text: shown.append(text))
    monkeypatch.setattr(overview.QFileDialog, "getSaveFileName",
                        lambda *a: (str(tmp_path / "interior.pdf"), ""))
    book = Project.create(tmp_path / "novel.candle", "Novel", "A. Writer")
    book.save_scene_content(book.list("scenes")[0]["id"], "<p>Once upon a time.</p>", "x")

    def make(session):
        dialog = overview.ExportDialog(book, None, session)
        dialog.format.setCurrentIndex(dialog.format.findData("kdp"))
        return dialog

    yield make, shown, tmp_path / "interior.pdf"
    book.close()


def test_kdp_export_needs_an_account(kdp_dialog):
    make, shown, pdf = kdp_dialog
    make(None)._export()
    assert "Candle Premium" in shown[0] and "Sign in" in shown[0]
    assert not pdf.exists()


def test_kdp_export_needs_premium(kdp_dialog, servers):
    make, shown, pdf = kdp_dialog
    dialog = make(signed_in())
    dialog._export()
    assert wait_for(lambda: shown)
    assert "Get it in" in shown[0]
    assert not pdf.exists()


def test_kdp_export_for_premium(kdp_dialog, servers):
    make, shown, pdf = kdp_dialog
    servers.me = {**servers.me, "premium": True}
    dialog = make(signed_in())
    dialog.trim.setCurrentText("5 × 8 in (12.7 × 20.32 cm)")
    dialog._export()
    assert wait_for(pdf.exists)
    assert pdf.read_bytes().startswith(b"%PDF")
    assert "Trim size: <b>5 × 8 in</b>" in shown[0] and "No bleed" in shown[0]


def test_no_kdp_option_without_the_service(qapp, tmp_path, monkeypatch):
    from candle.views import overview
    monkeypatch.setattr(cloud, "API_URL", "")
    book = Project.create(tmp_path / "n.candle", "Novel", "")
    try:
        assert overview.ExportDialog(book).format.findData("kdp") == -1
    finally:
        book.close()


def test_premium_window_offers_the_free_trial(qapp, servers):
    from candle import account
    servers.me = {**servers.me, "trial_days": 7}
    dialog = account.PremiumDialog(signed_in())
    try:
        assert wait_for(lambda: dialog.plan_buttons)
        assert [b.text() for b in dialog.plan_buttons] == ["Free trial, then US$36 / year", "Free trial, then US$4 / month"]
        assert "free for 7 days" in dialog.status.text() and "Goals, with Wick" in dialog.features.text()
    finally:
        dialog.close()
    servers.me = {**servers.me, "premium": True, "plans": [], "trial_ends": "2027-01-01T12:00:00+00:00"}
    dialog = account.PremiumDialog(signed_in())
    try:
        assert wait_for(lambda: "free trial" in dialog.status.text())
        assert "January 2027" in dialog.status.text() and dialog.plan_buttons == []
    finally:
        dialog.close()
