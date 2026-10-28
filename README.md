<p align="center"><img src="candle/resources/candle.png" width="128" alt="Candle icon: a lit candle with a quill"></p>

# Candle

**A quiet place to write your novel.** Candle is free, open-source software for
planning and writing novels on Linux, Windows and macOS. It is inspired by
[bibisco](https://bibisco.com): you plan the story's architecture, build your
characters, locations and plot lines, then write it chapter by chapter, scene
by scene.

No accounts, no ads, no cloud. Your novels stay on your computer.

## Install

### Linux (Snap)

```bash
sudo snap install candle-writer
```

Candle then appears in your applications menu. To open projects stored on USB
drives or other external disks, also run:

```bash
sudo snap connect candle-writer:removable-media
```

### Windows

1. Download `Candle-<version>-windows-setup.exe` from the
   [latest release](https://github.com/lmtrarbach/candle/releases/latest).
2. Run it. Windows may say "Windows protected your PC", because Candle isn't
   signed with a paid certificate. Click **More info → Run anyway**.

If you'd rather not install anything, the `windows-portable.zip` runs straight
from a folder.

### macOS (Apple Silicon)

New macOS builds are paused for now. Version 0.1.1 is available, or you can run
the latest version [from source](#from-source).

1. Download `Candle-0.1.1-macos-arm64.dmg` from
   [release v0.1.1](https://github.com/lmtrarbach/candle/releases/tag/v0.1.1).
2. Open it and drag **Candle** into **Applications**.
3. The first time, macOS says Candle "can't be verified", because it isn't
   signed with a paid Apple certificate. Open **System Settings → Privacy &
   Security**, scroll down and click **Open Anyway**. You only need to do this
   once.

### From source

You need Python 3.10 or newer and git.

**Linux**

```bash
git clone https://github.com/lmtrarbach/candle.git
cd candle
./run.sh                  # the first run sets everything up, then opens Candle
./install-desktop.sh      # optional: add Candle to your applications menu
```

On Debian or Ubuntu, if `./run.sh` complains about `venv`, run
`sudo apt install python3-venv` first.

**Windows or macOS**

```bash
git clone https://github.com/lmtrarbach/candle.git
cd candle
python3 -m venv .venv
.venv/bin/pip install .            # Windows: .venv\Scripts\pip install .
.venv/bin/candle                   # Windows: .venv\Scripts\candle
```

## What it does

| Section | What you get |
|---|---|
| **Project** | Title, author, language, a target length and a daily word goal, with progress bars |
| **Architecture** | Premise, fabula, setting, themes, notes, and narrative strands (plot lines) |
| **Chapters** | Chapters and scenes in a tree. Each scene has a rich-text editor, a status (to do / in progress / done), point of view, location, story time, linked characters, strands and objects, notes, and saved revisions you can restore |
| **Characters** | Main characters get an interview of about 45 questions in 9 sections (bibisco-style); secondary characters get a description |
| **Locations / Objects** | A description for each, plus nation, region and city for locations |
| **Timeline** | All scenes sorted by when they happen in the story, or by reading order. Double-click a row to open the scene |
| **Analysis** | Word counts, chapter lengths, and grids showing which characters, locations and strands appear in each chapter |

**Writing comforts**
- Full view (Ctrl+Shift+F, or the button on any scene) gives the whole window
  to the text, keeping the toolbar and word count.
- Focus mode (F11) shows only the text, full screen.
- Light and dark themes, or follow the system setting.
- Live word count, plus a counter for words written today.
- Find (Ctrl+F) in the current text.
- Pasted text is cleaned of foreign fonts and colours.

On macOS, use Cmd wherever these instructions say Ctrl.

**Export** (File → Export, Ctrl+Shift+E) to Markdown, HTML, plain text, ODT,
PDF, DOCX or EPUB 3. You can choose whether to include a title page, chapter
titles and chapter numbers, and whether to export only scenes marked *Done*.

## Your files

A project is a single `.candle` file, which is an ordinary SQLite database. You
choose where it lives, and Candle saves as you type. Each time you open a
project, Candle also writes a timestamped backup and keeps the last 10 per
project. **Help → About Candle** shows the backup folder on your system.

## Support Candle

Candle is free and open source, and always will be. If it helps you write,
you can support its development with a donation:

| Coin | Address |
|---|---|
| Bitcoin | `bc1qnyceh488yqr0l6ffljygf47243p8wsvct4mkw7` |
| Ethereum | `0x8bc6D2D3d47D15EEd881975A09F008609F3bAdF2` |
| Solana | `3Gq3t2Xoix8eRvyxCE8mdB5BPsNCwHxDVc8oLXMTeFe1` |

The same addresses, with copy buttons, are in the app under **Help → Support Candle**.

Bug reports and ideas are welcome too, in
[Issues](https://github.com/lmtrarbach/candle/issues).

## Develop

```bash
git clone https://github.com/lmtrarbach/candle.git && cd candle
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m candle
```

```
candle/
  app.py          main window, menus, themes, full view and focus mode, recent files
  about.py        About window and donation addresses
  db.py           project storage (SQLite schema and queries)
  richtext.py     editor HTML → clean paragraph model (used by export and paste)
  export.py       md / html / txt / odt / pdf / docx / epub writers
  widgets.py      rich text editor, check lists, autosave debouncer
  questions.py    character interview and architecture prompts
  views/          one module per section of the app
packaging/        PyInstaller recipe, Windows installer script, icons
snap/             Snap Store package
```

To change the icon, edit `candle/resources/candle.svg` and run
`python packaging/make_icons.py` (needs Pillow).

## Releasing

| Platform | Output | Built by |
|---|---|---|
| Linux | `.snap`, published to the Snap Store | `snap/snapcraft.yaml` |
| Windows | installer `.exe` + portable `.zip` | `packaging/candle.spec` (PyInstaller) + `packaging/candle.iss` (Inno Setup) |
| macOS (Apple Silicon), *paused* | `.dmg` containing `Candle.app` | `packaging/candle.spec` + `hdiutil`; re-enable the `macos` job in the workflow |
| Microsoft Store | `.msix` (signed by Microsoft on submission) | `packaging/msix/AppxManifest.xml` + `makeappx` |

To release, bump `__version__` in `candle/__init__.py`, then tag and push:

```bash
git tag v0.1.1 && git push origin v0.1.1
```

`.github/workflows/release.yml` then runs the tests, builds all three platforms
on GitHub's machines, creates a GitHub release with the files, and publishes
the snap to the Snap Store's stable channel. The `.msix` for the Microsoft
Store is attached to the workflow run (not the release), to upload in Partner
Center. Store text, screenshots and the privacy policy are in `packaging/store/`
and `PRIVACY.md`.

### Publishing the snap (one-time setup)

1. Create an account at [snapcraft.io](https://snapcraft.io).
2. On your computer:

   ```bash
   sudo snap install snapcraft --classic
   snapcraft login
   snapcraft register candle-writer
   snapcraft export-login --snaps=candle-writer \
       --acls package_access,package_push,package_update,package_release snap-login.txt
   gh secret set SNAPCRAFT_STORE_CREDENTIALS --repo lmtrarbach/candle < snap-login.txt
   rm snap-login.txt     # it's a password: don't keep it or commit it
   ```

Until that secret exists, releases still build the `.snap` and attach it to
the GitHub release. They just skip the Snap Store step.

To build and try the snap locally:

```bash
sudo snap install lxd && sudo lxd init --auto && sudo usermod -aG lxd "$USER"   # then log out and back in
snapcraft
sudo snap install --dangerous ./candle-writer_*.snap
```

## License

Candle is free software, released under the [GNU General Public License v3.0](LICENSE).
