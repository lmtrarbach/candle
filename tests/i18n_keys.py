"""Every English text Candle shows, as the keys of candle/resources/i18n/<language>.json.

    python -m tests.i18n_keys            # all keys, as JSON
    python -m tests.i18n_keys fr         # the keys fr.json lacks

Keys come from t("…") and tn(n, "…", "…") calls (always string literals, found in the code's
syntax tree), and from the English data shown translated: the interview and architecture
(questions.py), Lighter's lines (coach.LINES), export formats and KDP papers; and the messages
Candle's server can answer with (server-messages.json, kept equal to the server's by its tests).
"""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CANDLE = ROOT / "candle"
FOLDER = CANDLE / "resources" / "i18n"


def code_keys():
    """{key: "text"|"plural"} from the calls in candle/."""
    keys = {}
    for path in sorted(CANDLE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            literal = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if node.func.id == "t" and literal and isinstance(node.args[0], ast.Constant):
                keys.setdefault(literal[0], "text")
            elif node.func.id == "tn" and len(literal) >= 2:
                keys[literal[1]] = "plural"
    return keys


def data_keys():
    sys.path.insert(0, str(ROOT))
    from candle import coach, export, kdp, questions

    keys = []
    for _, title, items in questions.CHARACTER_SECTIONS:
        keys += [title, *items]
    for _, title, prompt in questions.ARCHITECTURE_SECTIONS:
        keys += [title, prompt]
    keys += [line for lines in coach.LINES.values() for line in lines]
    keys += list(export.FORMATS) + list(kdp.PAPERS)
    keys += json.loads((FOLDER / "server-messages.json").read_text(encoding="utf-8"))
    return keys


def all_keys():
    keys = code_keys()
    for key in data_keys():
        keys.setdefault(key, "text")
    return keys


def missing(language):
    catalog = json.loads((FOLDER / f"{language}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in all_keys().items() if k not in catalog}


if __name__ == "__main__":
    found = missing(sys.argv[1]) if len(sys.argv) > 1 else all_keys()
    print(json.dumps(found, ensure_ascii=False, indent=1))
