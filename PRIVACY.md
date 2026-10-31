# Candle privacy policy

*Last updated: 28 October 2026*

Candle (also published as "Candle Writer") is a novel-writing app. This policy
covers every version of it: the Microsoft Store, Snap Store, GitHub downloads
and source code.

## Without an account, Candle collects no data

You don't need an account to use Candle. If you don't sign in:

- Candle has **no analytics**, **no tracking**, **no ads** and **no crash
  reporting**.
- Candle **never connects to the internet**. The only way it opens a web page is
  when you click a link in its About window, which opens in your own browser.
- Nothing you write is sent to the developer or to anyone else.

## What Candle stores on your computer

- **Your projects:** each novel is a `.candle` file saved where you choose.
- **Backups:** each time you open a project, Candle copies it into its own app
  data folder and keeps the last 10 copies. **Help → About Candle** shows that
  folder.
- **Settings:** your theme and a list of recently opened projects, kept in your
  user settings. If you sign in to Candle Premium, your email address and a
  sign-in token are kept there too, until you sign out.

You can delete any of these at any time. Uninstalling Candle removes its
settings. Your `.candle` files are never deleted automatically.

## Candle Premium (optional)

If you create an account and turn on cloud backup, this is what leaves your
computer, and why:

- **Your email address**, and your password if you choose one instead of
  signing in with Google. You sign in on a Candle page in your browser, which
  sends them to Google Firebase Authentication; Candle itself and the
  developer never see your password. Your email is used only for your
  account: confirming your address, resetting your password, and important
  notices about the service.
- **Payment details**, if you buy Candle Premium: you pay on a Stripe page,
  and your card details go only to Stripe. Candle's service keeps the Stripe
  customer id linked to your account, to know whether your subscription is
  active. Deleting your account cancels the subscription.
- **Copies of your projects**, uploaded to a private Google Cloud Storage
  bucket, so you can restore them. Each account's backups are kept in a
  separate folder that only that account can open. They are encrypted at rest
  by Google Cloud. The latest 20 backups of each project are kept, and older
  ones are deleted automatically.
- **KDP files made on the web dashboard.** If you make a KDP paperback PDF on
  the web dashboard (rather than in Candle), the service reads the backup you
  chose, which is already stored there, lays it out, and sends you the PDF.
  The PDF isn't kept. In Candle itself, the book is laid out on your computer.
- **Goals and reminders.** Your goals (daily goal, days a week, deadline,
  reminder time) are saved in the project file, so they're in its backups.
  If you turn on reminders in your browser, the service keeps that browser's
  push address (given by its maker: Google, Mozilla, Apple or Microsoft), its
  time zone and the reminder time of each project, to send the reminder.
  At that time it reads the project's latest backup to see whether you've met
  the day's goal; the reminder contains only Lighter's message and the project's
  title. Turning the reminder off, or deleting your account, deletes them.
- **Basic request logs** (time, address, and which request was made, but never
  the contents of your projects), kept by Google Cloud for running and securing
  the service.

The developer doesn't read your backups, and never sells or shares your data.
Google acts as the service's data processor.

**Deleting your data:** in Candle, **Account → Account… → Delete account**
deletes your account and every cloud backup straight away. Deleted backups
stay recoverable by the developer for up to 30 days, as a protection against
mistakes, and are then gone for good. You can also delete the backups of one
project from **Account → Restore from cloud…**.

## The website (candlewriter.com)

The landing page at candlewriter.com can use Google Analytics to count
visits and see which links are used (for example, which download button).
It only does so if you choose **Accept** when it asks; choose **No thanks**
and nothing is loaded. Your choice is kept in your browser, and **Cookie
settings** at the bottom of the page lets you change it. Google Analytics
isn't used in Candle, in Candle on the web, on your account page or on
review pages, where your writing is.

## Changes to this policy

If this policy ever changes, the new version will be published at
<https://github.com/lmtrarbach/candle/blob/main/PRIVACY.md>, and its history is
public in the repository.

## Contact

Questions about your account, Candle Premium, a payment or your data (for
example, to ask what's stored or to have it deleted): email
<luthiano.trarbach@proton.me>. For anything else, open an issue at
<https://github.com/lmtrarbach/candle/issues>.
