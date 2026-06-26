# -*- coding: utf-8 -*-
"""Patches index.html's P dict (109 ingredients) with freshly scraped
stock_data.json -- refreshes product/price/unit/inStock/ean/alts for every
key, but always preserves our own nm (English display name) and ic (icon),
which aren't scraped.

Defensive for unattended/scheduled use: if a given key's fresh scrape came
back with no match (or a match missing required fields), that key's
existing line is left completely untouched rather than overwritten with
incomplete data -- a transient search miss on one ingredient should never
corrupt the rest of the P dict."""
import json
import re
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "index.html"
STOCK_PATH = Path(__file__).parent / "stock_data.json"

LINE_RE = re.compile(r'^(\w+):\{"nm":\s*"([^"]*)",\s*"ic":\s*"([^"]*)",.*\}$')


def js_field(name, value):
    if isinstance(value, bool):
        return f'"{name}": {"true" if value else "false"}'
    if isinstance(value, (int, float)):
        return f'"{name}": {value}'
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{name}": "{escaped}"'


def build_alt(cand):
    return ('{' + ', '.join([
        js_field('product', cand['name']),
        js_field('price', cand['price']),
        js_field('unit', cand['unit']),
        js_field('ean', cand['ean']),
        js_field('inStock', bool(cand['inStockAtStore'])),
    ]) + '}')


def build_line(key, nm, ic, match, alternates):
    parts = [
        js_field('nm', nm), js_field('ic', ic),
        js_field('product', match['name']), js_field('price', match['price']),
        js_field('unit', match['unit']), js_field('inStock', bool(match['inStockAtStore'])),
        js_field('ean', match['ean']),
    ]
    line = key + ':{' + ', '.join(parts) + '}'
    if alternates:
        alts_js = '[' + ','.join(build_alt(a) for a in alternates) + ']'
        line = line[:-1] + ',"alts":' + alts_js + '}'
    return line + ','


def main():
    stock = json.load(open(STOCK_PATH, encoding="utf-8"))
    products = stock['products']

    html = HTML_PATH.read_text(encoding="utf-8")
    start_marker = "\nconst P={\n"
    end_marker = "\n};\n"
    assert html.count(start_marker) == 1, "expected exactly one P dict start marker"
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    body = html[start:end]

    lines = [l for l in body.split('\n') if l.strip()]
    new_lines = []
    updated, skipped_no_match, skipped_incomplete, missing_key = 0, [], [], []

    seen_keys = set()
    for line in lines:
        m = LINE_RE.match(line.rstrip(','))
        if not m:
            new_lines.append(line)  # unrecognized line shape -- leave untouched
            continue
        key, nm, ic = m.groups()
        seen_keys.add(key)
        entry = products.get(key)
        if not entry or not entry.get('match'):
            skipped_no_match.append(key)
            new_lines.append(line)
            continue
        match = entry['match']
        if not match.get('ean') or match.get('price') is None or not match.get('unit'):
            skipped_incomplete.append(key)
            new_lines.append(line)
            continue
        alternates = [a for a in entry.get('alternates', [])
                      if a.get('ean') and a.get('price') is not None and a.get('unit')]
        new_lines.append(build_line(key, nm, ic, match, alternates))
        updated += 1

    for key in products:
        if key not in seen_keys:
            missing_key.append(key)

    body_out = '\n'.join(l.rstrip(',') if i == len(new_lines) - 1 else l
                          for i, l in enumerate(new_lines))
    html_out = html[:start] + body_out + html[end:]

    print(f"Updated {updated}/{len(lines)} ingredients")
    if skipped_no_match:
        print(f"  kept stale (no match found): {skipped_no_match}")
    if skipped_incomplete:
        print(f"  kept stale (incomplete match): {skipped_incomplete}")
    if missing_key:
        print(f"  WARNING: stock_data.json has keys not present in P dict: {missing_key}")

    if updated == 0:
        print("Nothing updated -- not writing index.html")
        return False

    HTML_PATH.write_text(html_out, encoding="utf-8")
    print(f"Saved {HTML_PATH}")
    return True


if __name__ == "__main__":
    main()
