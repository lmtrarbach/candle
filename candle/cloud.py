"""Candle Premium: an optional account with cloud backups.

Nothing in this module runs until the writer signs in, so Candle stays fully
offline for everyone else. Signing in happens in the browser (see
`BrowserSignIn`), with Firebase Authentication; backups go through the Candle
Premium API, which hands out short-lived links to upload or download one file
in the writer's own private folder.

Blocking calls: run them off the UI thread (see `account.run_async`).
"""

import hmac
import http.server
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# The Candle Premium service (see candle_premium/README.md). The environment
# variables override these, e.g. to try a test deployment; set them empty to
# build or run Candle without Premium (the Account menu then stays hidden).
# The Firebase web API key is public by design: it identifies the project, it
# doesn't grant access to anything.
API_URL = os.environ.get("CANDLE_API_URL", "https://app.candlewriter.com").rstrip("/")
FIREBASE_API_KEY = os.environ.get("CANDLE_FIREBASE_KEY", "AIzaSyC0B4M8QHFwRCHV_nRRBMwszc1Xtps-5Uc")

# Help with an account, Candle Premium or a payment.
SUPPORT_EMAIL = "luthiano.trarbach@proton.me"

IDENTITY = "https://identitytoolkit.googleapis.com/v1/accounts:"
SECURE_TOKEN = "https://securetoken.googleapis.com/v1/token"
SQLITE_MAGIC = b"SQLite format 3\x00"

FIREBASE_ERRORS = {
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Wait a few minutes and try again.",
    "USER_DISABLED": "This account has been disabled.",
    "TOKEN_EXPIRED": "Your session has expired. Sign in again.",
    "INVALID_REFRESH_TOKEN": "Your session has expired. Sign in again.",
    "USER_NOT_FOUND": "Your session has expired. Sign in again.",
}
SESSION_ENDED = {"TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN", "USER_NOT_FOUND", "USER_DISABLED"}


def configured():
    """True when this build knows where the Premium service is."""
    return bool(API_URL and FIREBASE_API_KEY)


class CloudError(Exception):
    def __init__(self, message, status=0, session_ended=False):
        super().__init__(message)
        self.status = status
        self.session_ended = session_ended


def _http(method, url, *, json_body=None, form=None, data=None, headers=None, timeout=60):
    headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CloudError(f"Can't reach the Candle servers. Check your internet connection.\n\n({exc})")


def _firebase(endpoint, body):
    status, raw = _http("POST", f"{IDENTITY}{endpoint}?key={FIREBASE_API_KEY}", json_body=body)
    payload = json.loads(raw or b"{}")
    if status >= 400:
        code = payload.get("error", {}).get("message", "").split(" ")[0]
        raise CloudError(FIREBASE_ERRORS.get(code, f"Sign-in failed ({code or status})."),
                         status, code in SESSION_ENDED)
    return payload


def plans():
    """What Premium costs; public, so it can be shown before signing in."""
    status, raw = _http("GET", f"{API_URL}/v1/plans")
    if status >= 400:
        raise CloudError(f"The Candle server answered with an error ({status}).", status)
    return json.loads(raw)


class Session:
    """A signed-in account. Keeps the long-lived refresh token and trades it
    for short-lived ID tokens, which the API checks on every call."""

    def __init__(self, email, refresh_token):
        self.email = email
        self.refresh_token = refresh_token
        self._id_token = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def send_verification(self):
        _firebase("sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": self.id_token()})

    def id_token(self, force=False):
        with self._lock:
            if force or not self._id_token or time.time() >= self._expires:
                status, raw = _http("POST", f"{SECURE_TOKEN}?key={FIREBASE_API_KEY}",
                                    form={"grant_type": "refresh_token", "refresh_token": self.refresh_token})
                payload = json.loads(raw or b"{}")
                if status >= 400:
                    code = payload.get("error", {}).get("message", "").split(" ")[0]
                    raise CloudError(FIREBASE_ERRORS.get(code, "Sign in again."), status, True)
                self.refresh_token = payload["refresh_token"]
                self._id_token = payload["id_token"]
                self._expires = time.time() + int(payload.get("expires_in", 3600)) - 60
            return self._id_token

    # -- API --------------------------------------------------------------
    def _api(self, method, path, body=None, retry=True):
        status, raw = _http(method, f"{API_URL}{path}", json_body=body,
                            headers={"Authorization": f"Bearer {self.id_token()}"})
        if status == 401 and retry:
            self.id_token(force=True)
            return self._api(method, path, body, retry=False)
        if status >= 400:
            try:
                detail = json.loads(raw).get("detail")
            except ValueError:
                detail = None
            raise CloudError(detail or f"The Candle server answered with an error ({status}).",
                             status, status == 401)
        return json.loads(raw) if raw else None

    def me(self):
        # Fresh token, so a just-confirmed email or new Premium shows up at once.
        self.id_token(force=True)
        return self._api("GET", "/v1/me")

    def projects(self):
        return self._api("GET", "/v1/projects")

    def backups(self, project_id):
        return self._api("GET", f"/v1/projects/{project_id}/backups")

    def upload(self, project_id, title, path):
        started = self._api("POST", f"/v1/projects/{project_id}/backups", {"title": title})
        upload = started["upload"]
        with open(path, "rb") as f:
            data = f.read()
        status, raw = _http(upload["method"], upload["url"], data=data, headers=upload["headers"], timeout=300)
        if status >= 400:
            raise CloudError(f"The upload failed ({status}).", status)
        return self._api("POST", f"/v1/projects/{project_id}/backups/{started['backup_id']}/complete")

    def download(self, project_id, backup_id, target):
        url = self._api("GET", f"/v1/projects/{project_id}/backups/{backup_id}/download")["url"]
        status, data = _http("GET", url, timeout=300)
        if status >= 400 or not data.startswith(SQLITE_MAGIC):
            raise CloudError(f"The download failed ({status}).", status)
        with open(target, "xb") as f:
            f.write(data)
        return target

    def checkout_url(self, plan):
        """A Stripe page, for this account only, where the writer pays for Premium.
        `plan` is one of the plans `me()` offers ("monthly", "yearly")."""
        return self._api("POST", "/v1/billing/checkout", {"plan": plan})["url"]

    def billing_portal_url(self):
        """A Stripe page to change the card, see invoices or cancel."""
        return self._api("POST", "/v1/billing/portal")["url"]

    def delete_project(self, project_id):
        self._api("DELETE", f"/v1/projects/{project_id}")

    def delete_account(self):
        self._api("DELETE", "/v1/account")


SIGNED_IN_PAGE = b"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Signed in to Candle</title>
<style>body{font:17px/1.5 system-ui,sans-serif;max-width:30em;margin:15vh auto;padding:0 16px;
color:#222;background:#fdfbf7}@media(prefers-color-scheme:dark){body{color:#eee;background:#1d1c1a}}</style>
</head><body><h1>You're signed in</h1><p>Go back to Candle. You can close this tab.</p></body></html>"""


class BrowserSignIn:
    """Sign in or create an account in the browser, on the API's /signin page.

    The page posts the session to a one-time address on this computer
    (127.0.0.1, a random port: the "loopback redirect" of RFC 8252). It must
    carry the random `state` put in the link, so only the page Candle opened
    can sign Candle in. Blocking: call wait() off the UI thread.
    """

    def __init__(self):
        self.state = secrets.token_urlsafe(32)
        self._received = None
        self._cancelled = threading.Event()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            timeout = 10   # a browser's idle pre-connection mustn't hold the wait up

            def do_POST(self):
                owner._receive(self)

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._server.timeout = 0.25
        self.url = f"{API_URL}/signin#port={self._server.server_port}&state={self.state}"

    def _receive(self, request):
        length = min(int(request.headers.get("Content-Length") or 0), 64 * 1024)
        form = urllib.parse.parse_qs(request.rfile.read(length).decode("utf-8", "replace"))
        state, email, token = ((form.get(k) or [""])[0] for k in ("state", "email", "refresh_token"))
        # Browsers send our page's origin, or "null" under its no-referrer policy.
        origin_ok = request.headers.get("Origin") in (None, "null", _origin(API_URL))
        if request.path == "/callback" and origin_ok and token and hmac.compare_digest(state, self.state):
            self._received = (email, token)
            request.send_response(200)
            request.send_header("Content-Type", "text/html; charset=utf-8")
            request.end_headers()
            request.wfile.write(SIGNED_IN_PAGE)
        else:
            request.send_error(400)

    def wait(self, timeout=15 * 60):
        """The new Session, once the browser hands it over."""
        deadline = time.monotonic() + timeout
        try:
            while self._received is None:
                if self._cancelled.is_set():
                    raise CloudError("Sign-in cancelled.")
                if time.monotonic() > deadline:
                    raise CloudError("Sign-in took too long. Try again.")
                self._server.handle_request()
        finally:
            self._server.server_close()
        session = Session(*self._received)
        session.id_token(force=True)   # make sure it works before keeping it
        return session

    def cancel(self):
        self._cancelled.set()


def _origin(url):
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
