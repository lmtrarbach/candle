# Changelog

## Unreleased

- **Wick is now Lighter.** One writing companion, Lighter, keeps you going with
  your goals (and, on the web, asks small questions about your story). On the
  Goals page it's an open lighter whose flame shows how the writing is going;
  its lid is shut when you've been away a while.
- **A free account does more.** Signed in without Premium, Candle backs up the
  latest version of each project, and you can write your projects on the web.
  The Premium window lists what Premium adds: Lighter, the latest 20 versions
  of every project, Amazon KDP paperbacks and reviews.

## 0.3.0 — 2026-10-30

### Goals, with Wick, your writing companion (Candle Premium)

- **Goals page.** Set a daily goal in words or pages (250 words a page), how
  many days a week you write, a target length and a deadline. Goals are saved
  in the project, so Candle on the web shows the same ones.
- **Wick** keeps you going: a small candle whose flame burns bright when
  you've met the day's goal and flickers when your streak is at risk. It
  cheers, nudges and welcomes you back, with a new line each day.
- **Streaks.** Days in a row you've met your goal (shown in the status bar),
  or weeks in a row if you write on fewer than seven days a week, and this
  week at a glance.
- **Deadlines.** Wick works out how much you need to write each day to reach
  your target length by the date you chose.
- **Reminders.** At the time you choose, if you haven't met the day's goal
  yet: a desktop notification while Candle is open, and in Candle on the web,
  a browser notification even when it's closed.

### Candle Premium

- **Free trial.** First-time subscribers get 7 days of Premium free: **Account
  → Candle Premium…** offers it, and while it lasts shows when it ends and how
  to cancel without being charged.

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
- **Candle on the web** (Premium, https://app.candlewriter.com): everything
  Candle does, in the browser: the project's details and goals, the
  architecture, chapters and scenes (details panel, links, revisions, focus
  mode), characters with the interview, locations, objects, strands, the
  timeline and the analysis, plus KDP export. Saving makes a new cloud
  version; when the project is next opened in Candle and this file hasn't
  changed since its last backup, Candle offers to bring the web version in
  (keeping this file's cloud link and daily word counts). If both changed,
  nothing is merged: the web version can be saved as a separate file.
- **Web dashboard.** **Account → Open web dashboard** (or the service's
  `/account` page, from any computer) lists every project in the cloud and
  every backup version: download any as a `.candle` file, or make a KDP
  paperback PDF from it (laid out on the server from that backup; the PDF
  isn't kept). It also shows the plan and opens checkout or the billing
  portal.
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

- The Premium service lives at `https://app.candlewriter.com` (the API, the
  sign-in page, the web dashboard at `/account`, and Candle on the web as
  the home page, `/`). That address and the Firebase Web API key are built into
  `candle/cloud.py`. `CANDLE_API_URL` and `CANDLE_FIREBASE_KEY` override them
  (for a test deployment); set them empty to run without Premium. The
  Firebase Web API key is public by design: it identifies the project and is
  restricted to the sign-in APIs. Stripe keys and every other secret live only
  on the server, in Google Secret Manager.
