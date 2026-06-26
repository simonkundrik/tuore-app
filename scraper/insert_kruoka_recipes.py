# -*- coding: utf-8 -*-
"""Serializes kruoka_recipes.json into the same single-line minified JS
object literal format already used for every other recipe in index.html's
`meals` array, and splices them into the array.

Idempotent: every recipe this pipeline generates gets an id starting with
'kr' (see build_kruoka_recipes.py's make_id(['kr', ...])), so a re-run
first strips any 'kr*' entries left by a previous run before inserting the
freshly rebuilt batch -- safe to run on a schedule without the recipe
count growing unbounded."""
import json
import re
from pathlib import Path

HTML_PATH = Path(r"C:\Users\swath\tuore-app\index.html")


def js_str(s, quote="'"):
    return quote + s.replace('\\', '\\\\').replace(quote, '\\' + quote) + quote


def js_arr(items, quote="'"):
    return '[' + ','.join(js_str(x, quote) for x in items) + ']'


DQ = chr(34)


def serialize(r):
    parts = [
        f"id:{js_str(r['id'])}",
        f"name:{js_str(r['name'], DQ)}",
        f"icon:{js_str(r['icon'])}",
        f"type:{js_arr(r['type'])}",
        f"filters:{js_arr(r['filters'])}",
        f"tags:{js_arr(r['tags'])}",
        f"time:{r['time']}",
        f"protein:{r['protein']}",
        f"carbs:{r['carbs']}",
        f"fat:{r['fat']}",
        f"kcal:{r['kcal']}",
        f"servings:{r['servings']}",
        f"equip:{js_arr(r['equip'])}",
        f"steps:{js_arr(r['steps'], DQ)}",
        "ing:[" + ','.join(f"{{ref:{js_str(i['ref'])},frac:{i['frac']}}}" for i in r['ing']) + ']',
    ]
    if r.get('photo'):
        parts.append(f"photo:{js_str(r['photo'])}")
    return '{' + ','.join(parts) + '}'


def main():
    recipes = json.load(open(Path(__file__).parent / "kruoka_recipes.json", encoding="utf-8"))
    html = HTML_PATH.read_text(encoding="utf-8")

    start_marker = "\nlet meals=[\n"
    end_marker = "\n];\n\nconst EQNAMES="
    assert html.count(start_marker) == 1, f"expected exactly one start marker, found {html.count(start_marker)}"
    assert html.count(end_marker) == 1, f"expected exactly one end marker, found {html.count(end_marker)}"

    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    body = html[start:end]

    existing_lines = [l for l in body.split('\n') if l.strip()]
    kept = [l for l in existing_lines if not re.match(r"\{id:'kr", l)]
    removed = len(existing_lines) - len(kept)

    new_lines = [serialize(r) for r in recipes]
    all_lines = kept + new_lines
    # every line needs a trailing comma except the last
    body_out = ',\n'.join(l.rstrip(',') for l in all_lines)

    html = html[:start] + body_out + html[end:]
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Removed {removed} stale kr* recipes, inserted {len(recipes)} fresh ones "
          f"({len(all_lines)} total in meals array)")


if __name__ == "__main__":
    main()
