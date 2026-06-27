# -*- coding: utf-8 -*-
"""Appends airfryer_recipes.json into the `let meals=[...]` array in
index.html, right before its closing `];`. Idempotent: skips any recipe
whose id is already present (recipe_lib.existing_ids), so a re-run after
the recipes are already inserted is a safe no-op rather than a duplicate."""
import json
from pathlib import Path
from recipe_lib import existing_ids

HTML_PATH = Path(__file__).parent.parent / "index.html"
DATA_PATH = Path(__file__).parent / "airfryer_recipes.json"


def js_str(r):
    def arr(lst): return '[' + ','.join(f"'{x}'" for x in lst) + ']'
    def ingarr(ing): return '[' + ','.join(f"{{ref:'{i['ref']}',frac:{i['frac']}}}" for i in ing) + ']'
    def steparr(steps): return '[' + ','.join(json.dumps(s, ensure_ascii=False) for s in steps) + ']'
    name_js = json.dumps(r['name'], ensure_ascii=False)
    return (f"{{id:'{r['id']}',name:{name_js},icon:'{r['icon']}',type:{arr(r['type'])},"
            f"filters:{arr(r['filters'])},tags:{arr(r['tags'])},time:{r['time']},"
            f"protein:{r['protein']},carbs:{r['carbs']},fat:{r['fat']},kcal:{r['kcal']},servings:{r['servings']},"
            f"equip:{arr(r['equip'])},steps:{steparr(r['steps'])},ing:{ingarr(r['ing'])}}}")


def main():
    data = json.load(open(DATA_PATH, encoding="utf-8"))
    new_ones = [r for r in data if r['id'] not in existing_ids]
    skipped = len(data) - len(new_ones)
    if not new_ones:
        print(f"Nothing to insert -- all {len(data)} recipes already present")
        return

    html = HTML_PATH.read_text(encoding="utf-8")
    marker_start = html.index("\nlet meals=[")
    close_idx = html.index("\n];\n", marker_start)
    insertion = ",\n" + ",\n".join(js_str(r) for r in new_ones)
    html = html[:close_idx] + insertion + html[close_idx:]
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Inserted {len(new_ones)} new air-fryer recipes ({skipped} already present, skipped)")


if __name__ == "__main__":
    main()
