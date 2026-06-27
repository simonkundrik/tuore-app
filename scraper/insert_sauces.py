# -*- coding: utf-8 -*-
"""Serializes sauces_recommendations.json into a minified JS array literal
and inserts it right before the `let meals=[` declaration, same pattern
as insert_grabgo.py.

Idempotent: removes any existing `var SAUCES=[...]` block first, so a
scheduled re-run replaces last time's recommendations rather than leaving
a stale duplicate declaration behind."""
import json
import re
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "index.html"
DATA_PATH = Path(__file__).parent / "sauces_recommendations.json"

GROUP_ORDER = ['mayo', 'ketchup', 'mustard', 'bbq', 'hot_sauce', 'soy_sauce',
               'aioli', 'dressing', 'remoulade']


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
        f"fat100:{js_num(r.get('fat100'))}",
        f"fatSat100:{js_num(r.get('fatSat100'))}",
        f"carbs100:{js_num(r.get('carbs100'))}",
        f"sugar100:{js_num(r.get('sugar100'))}",
        f"salt100:{js_num(r.get('salt100'))}",
        f"dietTags:{js_arr_str(r.get('dietTags', []))}",
        f"badges:{js_arr_str(r.get('badges', []))}",
    ]
    return '{' + ','.join(parts) + '}'


def main():
    data = json.load(open(DATA_PATH, encoding="utf-8"))
    if not data:
        print("sauces_recommendations.json is empty -- leaving existing SAUCES block untouched")
        return
    data.sort(key=lambda r: GROUP_ORDER.index(r['group']) if r['group'] in GROUP_ORDER else 99)

    html = HTML_PATH.read_text(encoding="utf-8")

    existing_block = re.compile(r"\nvar SAUCES=\[\n.*?\n\];\n", re.DOTALL)
    html, n_removed = existing_block.subn("", html, count=1)

    marker = "\nlet meals=["
    assert html.count(marker) == 1, f"expected exactly one marker, found {html.count(marker)}"

    lines = [serialize(r) for r in data]
    js_array = "var SAUCES=[\n" + ",\n".join(lines) + "\n];\n"
    html = html.replace(marker, "\n" + js_array + "\nlet meals=[", 1)

    HTML_PATH.write_text(html, encoding="utf-8")
    status = "replaced previous batch" if n_removed else "first insertion"
    print(f"Inserted {len(data)} sauce recommendations into index.html ({status})")


if __name__ == "__main__":
    main()
