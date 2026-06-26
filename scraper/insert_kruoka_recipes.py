# -*- coding: utf-8 -*-
"""Serializes kruoka_recipes.json into the same single-line minified JS
object literal format already used for every other recipe in index.html's
`meals` array, and splices them in right before the closing `];`."""
import json
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

    marker = "\n];\n\nconst EQNAMES="
    assert html.count(marker) == 1, f"expected exactly one marker, found {html.count(marker)}"

    lines = [serialize(r) for r in recipes]
    insertion = ",\n" + ",\n".join(lines) + "\n];\n\nconst EQNAMES="
    html = html.replace(marker, insertion, 1)

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Inserted {len(recipes)} recipes into index.html")


if __name__ == "__main__":
    main()
