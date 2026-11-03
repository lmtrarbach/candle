"""Candle in ten languages: every text it shows is in every catalog, with its placeholders,
markup and menu shortcut intact."""

import json
import os
import re
import subprocess
import sys

import pytest

from candle import i18n
from tests import i18n_keys

LANGUAGES = [code for code in i18n.CODES if code != "en"]
KEYS = i18n_keys.all_keys()


def catalog(language):
    return json.loads((i18n_keys.FOLDER / f"{language}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_is_translated(language):
    """A new English text needs its translations before it ships (python -m tests.i18n_keys fr lists them)."""
    assert not i18n_keys.missing(language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_leftovers(language):
    """Texts Candle no longer shows leave the catalogs too."""
    assert set(catalog(language)) <= set(KEYS), set(catalog(language)) - set(KEYS)


@pytest.mark.parametrize("language", LANGUAGES)
def test_translations_keep_placeholders_markup_and_shortcuts(language):
    holes = lambda s: sorted(re.findall(r"\{\w+\}", s))
    tags = lambda s: sorted(re.findall(r"</?\w+[^>]*>", s))
    shortcuts = lambda s: len(re.findall(r"&(?!amp;)\S", s))
    for key, value in catalog(language).items():
        if KEYS[key] == "plural":
            assert isinstance(value, dict) and "other" in value, key
            assert all(holes(form) in ([], ["{n}"]) for form in value.values()), key
        else:
            assert isinstance(value, str) and value.strip(), key
            assert holes(value) == holes(key), (key, value)
            assert tags(value) == tags(key), (key, value)
            assert shortcuts(value) == shortcuts(key), (key, value)


def test_plural_categories():
    assert [i18n.plural(n, "en") for n in (0, 1, 2)] == ["other", "one", "other"]
    assert [i18n.plural(n, "fr") for n in (0, 1, 1.5, 2)] == ["one", "one", "one", "other"]
    assert [i18n.plural(n, "pt-BR") for n in (0, 1, 1.5, 2)] == ["one", "one", "other", "other"]
    assert {i18n.plural(n, lang) for n in (0, 1, 2) for lang in ("zh-CN", "ja")} == {"other"}


@pytest.mark.parametrize("language", ["fr", "hi", "ja"])
def test_candle_speaks_it(language):
    """The language is chosen at start-up: a fresh Candle in it, counts, server messages and all."""
    code = ("from candle.i18n import t, tn, translate_message as m;"
            "print(t('&File')); print(tn(3, '{n} word', '{n} words'));"
            "print(m('You can back up at most 5 projects.'))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                         env={**os.environ, "CANDLE_LANG": language}).stdout.splitlines()
    c = catalog(language)
    assert out == [c["&File"], c["{n} words"]["other"].replace("{n}", "3"),
                   c["You can back up at most {max_projects} projects."].replace("{max_projects}", "5")]


def test_english_without_qt():
    """coach.py and db.py also run on Candle's server, without Qt: there they speak English as before."""
    code = ("import importlib.util, datetime as d, sys;"
            "sys.modules['PySide6'] = None;"
            "s = importlib.util.spec_from_file_location('coach', 'candle/coach.py');"
            "c = importlib.util.module_from_spec(s); s.loader.exec_module(c);"
            "print(c.amount(1250, 'words'), '|', c.amount(500, 'pages'), '|', c.amount(1, 'words'))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                         cwd=i18n_keys.ROOT).stdout.strip()
    assert out == "1,250 words | 2 pages | 1 word"
