# -*- coding: utf-8 -*-
"""Serializes grabgo_recommendations.json into a minified JS array literal
(same style as the P dict / meals array already in index.html) and
inserts it right before the `let meals=[` declaration.

Idempotent: removes any existing `var GRABGO=[...]` block first, so a
scheduled re-run replaces last time's recommendations rather than leaving
a stale duplicate declaration behind."""
import json
import re
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "index.html"
DATA_PATH = Path(__file__).parent / "grabgo_recommendations.json"

GROUP_ORDER = ['fresh_fruit', 'berries', 'raw_veg_snack', 'dairy_snack', 'ready_meals',
               'ready_salads', 'deli', 'smoked_fish', 'nuts_snacks', 'dips']


def js_str(s, quote="'"):
    if s is None:
        return 'null'
    return quote + str(s).replace('\\', '\\\\').replace(quote, '\\' + quote) + quote


def js_num(n):
    return 'null' if n is None else str(n)


def js_arr_str(items):
    return '[' + ','.join(js_str(x) for x in items) + ']'


def serialize(r):
    parts = [
        f"ean:{js_str(r['ean'])}",
        f"name:{js_str(r['name'], chr(34))}",
        f"brand:{js_str(r.get('brand'), chr(34))}",
        f"group:{js_str(r['group'])}",
        f"groupLabel:{js_str(r['groupLabel'], chr(34))}",
        f"icon:{js_str(r['icon'])}",
        f"price:{js_num(r['price'])}",
        f"unit:{js_str(r.get('unit'))}",
        f"unitPrice:{js_num(r.get('unitPrice'))}",
        f"unitPriceUnit:{js_str(r.get('unitPriceUnit'))}",
        f"onSale:{'true' if r.get('onSale') else 'false'}",
        f"kcal100:{js_num(r['kcal100'])}",
        f"protein100:{js_num(r['protein100'])}",
        f"carbs100:{js_num(r.get('carbs100'))}",
        f"sugar100:{js_num(r.get('sugar100'))}",
        f"fiber100:{js_num(r.get('fiber100'))}",
        f"fat100:{js_num(r.get('fat100'))}",
        f"fatSat100:{js_num(r.get('fatSat100'))}",
        f"salt100:{js_num(r.get('salt100'))}",
        f"dietTags:{js_arr_str(r.get('dietTags', []))}",
        f"badges:{js_arr_str(r.get('badges', []))}",
        f"needsHeating:{'true' if r.get('needsHeating') else 'false'}",
        f"isWholeProduce:{'true' if r.get('isWholeProduce') else 'false'}",
    ]
    return '{' + ','.join(parts) + '}'


def main():
    data = json.load(open(DATA_PATH, encoding="utf-8"))
    if not data:
        print("grabgo_recommendations.json is empty -- leaving existing GRABGO block untouched")
        return
    data.sort(key=lambda r: GROUP_ORDER.index(r['group']))

    html = HTML_PATH.read_text(encoding="utf-8")

    existing_block = re.compile(r"\nvar GRABGO=\[\n.*?\n\];\n", re.DOTALL)
    html, n_removed = existing_block.subn("", html, count=1)

    marker = "\nlet meals=["
    assert html.count(marker) == 1, f"expected exactly one marker, found {html.count(marker)}"

    lines = [serialize(r) for r in data]
    js_array = "var GRABGO=[\n" + ",\n".join(lines) + "\n];\n"
    html = html.replace(marker, "\n" + js_array + "\nlet meals=[", 1)

    HTML_PATH.write_text(html, encoding="utf-8")
    status = "replaced previous batch" if n_removed else "first insertion"
    print(f"Inserted {len(data)} grab-and-go recommendations into index.html ({status})")


if __name__ == "__main__":
    main()
