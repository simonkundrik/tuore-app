# -*- coding: utf-8 -*-
"""One-off migration: retroactively adds lowfat/lowcal/verybudget filters
(and fixes the old inconsistent budget threshold) on every recipe already
baked into index.html's meals array. The three generator scripts already
compute these correctly for anything generated from now on, but most of
the ~1000 existing recipes were generated once and aren't part of any
scheduled re-run, so they need a direct retroactive fix."""
import re
from pathlib import Path
from recipe_lib import P, is_lowfat, is_lowcal, price_per_serving, BUDGET_MAX_EUR, VERYBUDGET_MAX_EUR

HTML_PATH = Path(__file__).parent.parent / "index.html"

ING_RE = re.compile(r"ing:\[(.*?)\]")
ING_ITEM_RE = re.compile(r"\{ref:'(\w+)',frac:([\d.]+)\}")
FILTERS_RE = re.compile(r"filters:\[([^\]]*)\]")
FAT_RE = re.compile(r"fat:([\d.]+)")
KCAL_RE = re.compile(r"kcal:([\d.]+)")
SERVINGS_RE = re.compile(r"servings:(\d+)")


def process_line(line):
    fat_m = FAT_RE.search(line)
    kcal_m = KCAL_RE.search(line)
    servings_m = SERVINGS_RE.search(line)
    ing_m = ING_RE.search(line)
    filters_m = FILTERS_RE.search(line)
    if not (fat_m and kcal_m and servings_m and ing_m and filters_m):
        return line, False

    fat = float(fat_m.group(1))
    kcal = float(kcal_m.group(1))
    servings = int(servings_m.group(1))
    ing_fracs = [(ref, float(frac)) for ref, frac in ING_ITEM_RE.findall(ing_m.group(1))]
    if not ing_fracs or any(ref not in P for ref, _ in ing_fracs):
        pps = None
    else:
        pps = price_per_serving(ing_fracs, servings)

    existing = [f.strip().strip("'\"") for f in filters_m.group(1).split(',') if f.strip()]
    base = [f for f in existing if f not in ('lowfat', 'lowcal', 'budget', 'verybudget')]

    new_filters = list(base)
    if is_lowfat(fat):
        new_filters.append('lowfat')
    if is_lowcal(kcal):
        new_filters.append('lowcal')
    if pps is not None and pps < BUDGET_MAX_EUR:
        new_filters.append('budget')
    if pps is not None and pps < VERYBUDGET_MAX_EUR:
        new_filters.append('verybudget')

    if new_filters == existing:
        return line, False

    new_filters_str = "filters:[" + ','.join(f"'{f}'" for f in new_filters) + "]"
    new_line = filters_m.group(0)
    line = line[:filters_m.start()] + new_filters_str + line[filters_m.end():]
    return line, True


def main():
    html = HTML_PATH.read_text(encoding="utf-8")
    start_marker = "\nlet meals=[\n"
    end_marker = "\n];\n\nconst EQNAMES="
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    body = html[start:end]
    lines = [l for l in body.split('\n') if l.strip()]

    changed = 0
    out_lines = []
    for l in lines:
        new_l, did_change = process_line(l.rstrip(','))
        if did_change:
            changed += 1
        out_lines.append(new_l)

    print(f"Updated filters on {changed}/{len(lines)} recipes")

    body_out = ',\n'.join(out_lines)
    html_new = html[:start] + body_out + html[end:]
    HTML_PATH.write_text(html_new, encoding="utf-8")
    print("Saved", HTML_PATH)


if __name__ == "__main__":
    main()
