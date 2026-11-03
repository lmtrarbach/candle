"""Candle in the writer's language. The English text is the key: t("Save") looks it up in
resources/i18n/<language>.json and falls back to English, so nothing is ever blank. Keys are
always a single string literal, which lets tests/test_i18n.py check every language has every one.
Placeholders are {name}: t("{n} of {goal}", n=…, goal=…).

The language is chosen once, when Candle starts (View → Language, else the computer's language),
so texts built at import time are already in it. Changing it takes effect after a restart.
"""

import json
import os
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings

LANGUAGES = [
    ("en", "English"), ("fr", "Français"), ("es", "Español"), ("pt-BR", "Português (Brasil)"),
    ("de", "Deutsch"), ("it", "Italiano"), ("nl", "Nederlands"), ("hi", "हिन्दी"),
    ("zh-CN", "简体中文"), ("ja", "日本語（横書き）"),   # Japanese: horizontal writing (yokogaki) only
]
CODES = [code for code, _ in LANGUAGES]
FOLDER = Path(__file__).parent / "resources" / "i18n"


def _pick():
    """CANDLE_LANG (tests), the writer's choice, else the computer's languages ("pt-PT" → "pt-BR")."""
    wanted = [os.environ.get("CANDLE_LANG") or QSettings("Candle", "Candle").value("language", "") or ""]
    wanted += [name.replace("_", "-") for name in QLocale.system().uiLanguages()]
    for name in filter(None, wanted):
        exact = next((c for c in CODES if c.lower() == name.lower()), None)
        base = next((c for c in CODES if c.split("-")[0] == name.split("-")[0].lower()), None)
        if exact or base:
            return exact or base
    return "en"


def _load(language):
    if language == "en":
        return {}
    try:
        return json.loads((FOLDER / f"{language}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


lang = _pick()
_catalog = _load(lang)
locale = QLocale(lang.replace("-", "_"))


def _fill(text, values):
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def t(key, **values):
    """The text in the writer's language."""
    found = _catalog.get(key)
    return _fill(found if isinstance(found, str) else (found or {}).get("other", key), values)


def plural(n, language=None):
    """CLDR's plural category for these languages: "one" or "other"."""
    language = (language or lang).split("-")[0]
    if language in ("zh", "ja"):             # no plural forms
        return "other"
    whole = int(abs(n)) == abs(n)
    if language in ("fr", "pt", "hi"):     # 0 and 1 (and 1.5 in French) are "one"
        return "one" if int(abs(n)) in (0, 1) and (whole or language == "fr") else "other"
    return "one" if abs(n) == 1 and whole else "other"


def number(n):
    """n written the way the language writes numbers (1,234 / 1 234 / 1.234)."""
    if isinstance(n, float) and not n.is_integer():
        return locale.toString(n, "f", 1)
    return locale.toString(int(n))


def long_date(day):
    """3 March 2027, the way the language writes it."""
    return locale.toString(day, "d MMMM yyyy")


def tn(n, one, other, **values):
    """A count: tn(n, "{n} word", "{n} words"). The catalog keeps every form a language
    needs, under the English plural: {"{n} words": {"one": …, "other": …}}."""
    forms = _catalog.get(other)
    if isinstance(forms, dict):
        text = forms.get(plural(n), forms.get("other", other))
    else:
        text = one if plural(n, "en") == "one" else other
    return _fill(text, {"n": number(n), **values})


_patterns = None


def translate_message(message):
    """A message from Candle's server (English) in the writer's language. Those with numbers
    or names match a catalog key's pattern: "…at most {max_projects} projects." """
    global _patterns
    if not message or not _catalog:
        return message
    if isinstance(_catalog.get(message), str):
        return _catalog[message]
    if _patterns is None:
        import re
        _patterns = []
        for key in (k for k in _catalog if "{" in k and isinstance(_catalog[k], str)):
            names = re.findall(r"\{(\w+)\}", key)
            source = re.sub(r"\\\{\w+\\\}", "(.+?)", re.escape(key))
            _patterns.append((key, names, re.compile(f"^{source}$", re.S)))
    for key, names, pattern in _patterns:
        found = pattern.match(message)
        if found:
            return t(key, **dict(zip(names, found.groups())))
    return message


def install_qt_translations(app):
    """Qt's own texts (OK, Cancel, Yes, file dialogs) in the writer's language, where Qt has them."""
    from PySide6.QtCore import QLibraryInfo, QTranslator

    QLocale.setDefault(locale)   # dates and numbers in Qt's own widgets, too
    translator = QTranslator(app)
    if translator.load(f"qtbase_{lang.replace('-', '_')}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
