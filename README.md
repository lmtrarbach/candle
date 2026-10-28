# Candle

A novel-writing tool for Linux, inspired by [bibisco](https://bibisco.com).
It's built with Python and Qt 6 (PySide6).

## Run it

```bash
./run.sh                      # first run creates .venv and installs dependencies
./run.sh ~/Documents/my-novel.candle
./install-desktop.sh          # optional: add Candle to your applications menu
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
- Focus mode (F11) shows only the text, full screen.
- Light and dark themes, or follow the system setting.
- Live word count, plus a counter for words written today.
- Find (Ctrl+F) in the current text.
- Pasted text is cleaned of foreign fonts and colours.

**Export** (File → Export, Ctrl+Shift+E) to Markdown, HTML, plain text, ODT,
PDF, DOCX or EPUB 3. You can choose whether to include a title page, chapter
titles and chapter numbers, and whether to export only scenes marked *Done*.

## Your files

A project is a single `.candle` file, which is an ordinary SQLite database, so
you can open it with any SQLite tool. Candle saves as you type. Each time you
open a project it also writes a timestamped backup to
`~/.local/share/Candle/Candle/backups/` and keeps the last 10 per project.

## Develop

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

```
candle/
  app.py          main window, menus, themes, focus mode, recent files
  db.py           project storage (SQLite schema and queries)
  richtext.py     editor HTML → clean paragraph model (used by export and paste)
  export.py       md / html / txt / odt / pdf / docx / epub writers
  widgets.py      rich text editor, check lists, autosave debouncer
  questions.py    character interview and architecture prompts
  views/          one module per section of the app
```

## Packaging

| Platform | Output | Built by |
|---|---|---|
| Linux | `.snap` | `snap/snapcraft.yaml` |
| Windows | installer `.exe` + portable `.zip` | `packaging/candle.spec` (PyInstaller) + `packaging/candle.iss` (Inno Setup) |
| macOS (Apple Silicon) | `.dmg` containing `Candle.app` | `packaging/candle.spec` + `hdiutil` |

Windows and macOS builds have to run on those systems.
`.github/workflows/release.yml` builds all three on GitHub's machines. Push a
tag such as `v0.1.0` and it publishes them as a GitHub release.

Build the snap locally:

```bash
sudo snap install snapcraft --classic
sudo snap install lxd && sudo lxd init --auto && sudo usermod -aG lxd "$USER"   # then log out and back in
snapcraft                                        # produces candle-writer_<version>_amd64.snap
sudo snap install --dangerous ./candle-writer_*.snap
```

Build a desktop bundle for the current OS: `pyinstaller packaging/candle.spec --noconfirm`.
To change the icon, edit `candle/resources/candle.svg` and run `python packaging/make_icons.py`.

## Ideas for next steps

- Spell checking (pyenchant + QSyntaxHighlighter)
- Importing a bibisco project archive
- Images for characters and locations
- Drag-and-drop reordering in the chapter tree
- Per-scene word goals and a writing-streak calendar

## License

Candle is free software, released under the [GNU General Public License v3.0](LICENSE).
