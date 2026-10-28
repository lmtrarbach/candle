# Changelog

## 0.2.0 — 2026-10-28

### Candle Premium (optional subscription)

Candle stays free and works offline. Signing in is optional; without an
account Candle never connects to the internet.

- **Sign in in the browser.** **Account → Sign in or create account…** opens a
  Candle page where you continue with Google or with an email and password.
  The page hands the session back to Candle through a one-time address on
  your own computer (`127.0.0.1`), protected by a random code. Candle never
  sees your password.
- **Cloud backup.** Each project is backed up when you open it, every hour
  while it's open, and on demand (**Account → Back up to cloud now**). The
  latest 20 backups of each project are kept, in a private folder only your
  account can open. **Account → Restore from cloud…** saves any of them as a
  new file and never overwrites one.
- **Print-ready Amazon KDP paperbacks.** **File → Export manuscript… → Amazon
  KDP paperback** lays out a PDF interior for any of KDP's 16 paperback trim
  sizes: the gutter follows KDP's page-count table, margins mirror on left
  and right pages, chapters open on right-hand pages, running heads and page
  numbers skip blank and opening pages, fonts are embedded. The book is laid
  out on your computer and never uploaded. Typesetting uses
  [Typst](https://typst.app).
- **Candle Premium window.** **Account → Candle Premium…** explains what
  Premium adds and what it costs, and lets you subscribe (monthly or yearly,
  through Stripe Checkout) or manage your subscription (Stripe's billing
  portal: switch plan, change card, cancel). Cancelling keeps Premium until
  the end of the paid period; backups stay downloadable afterwards.
- **Your account.** **Account → Account…** shows your plan and backup usage,
  resends the confirmation email, signs out, or deletes the account together
  with every cloud backup and any subscription.

### Other changes

- A **Save** button, **File → Save** (Ctrl+S) and a label that shows whether
  your latest changes are saved.
- Microsoft Store logos: poster art, box art and tile icon.
- `run.sh` removes the GTK and GLib paths that snap apps (such as VS Code's
  terminal) leak into the environment, which made GTK abort on start
  ("…does not contain a key named 'antialiasing'"), even when `$SNAP` isn't
  set.
- The snap asks for `network` (used only after signing in) and `network-bind`
  (the browser's sign-in hand-off on `127.0.0.1`).
- New dependency: `typst` (bundled by PyInstaller and the snap).
- `PRIVACY.md` describes what Candle Premium sends, to whom, and why.

### For developers

- The Premium service address and Firebase Web API key are built into
  `candle/cloud.py`. `CANDLE_API_URL` and `CANDLE_FIREBASE_KEY` override them
  (for a test deployment); set them empty to run without Premium. The
  Firebase Web API key is public by design: it identifies the project and is
  restricted to the sign-in APIs. Stripe keys and every other secret live only
  on the server, in Google Secret Manager.
