# -*- coding: utf-8 -*-
"""Patches recipe_stock_photos.json's entries into index.html's meals array
as a new `stockPhoto:{url,photographer,photographerUrl}` field. Idempotent:
skips any id that already has a `photo:` (real K-Ruoka photo) or
`stockPhoto:` field, so re-running after some entries are already patched
only touches the remaining ones."""
import json
import re
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "index.html"
DATA_PATH = Path(__file__).parent / "recipe_stock_photos.json"


def js_str(s):
    return "'" + str(s).replace('\\', '\\\\').replace("'", "\\'") + "'"


def main():
    photos = json.load(open(DATA_PATH, encoding="utf-8"))
    html = HTML_PATH.read_text(encoding="utf-8")

    meals_start = html.index("\nlet meals=[")
    meals_end = html.index("\n];\n", meals_start)
    block = html[meals_start:meals_end]
    lines = block.split('\n')

    patched = 0
    for i, line in enumerate(lines):
        m = re.match(r"\{id:'([^']+)',", line)
        if not m:
            continue
        mid = m.group(1)
        if mid not in photos:
            continue
        if "photo:'" in line or 'stockPhoto:' in line:
            continue
        p = photos[mid]
        field = (f",stockPhoto:{{url:{js_str(p['url'])},photographer:{js_str(p['photographer'])},"
                 f"photographerUrl:{js_str(p['photographerUrl'])}}}")
        assert line.endswith('},') or line.endswith('}')
        if line.endswith('},'):
            lines[i] = line[:-2] + field + '},'
        else:
            lines[i] = line[:-1] + field + '}'
        patched += 1

    if not patched:
        print("Nothing to patch -- no matching ids without an existing photo")
        return

    html = html[:meals_start] + '\n'.join(lines) + html[meals_end:]
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"Patched stockPhoto onto {patched} recipe(s)")


if __name__ == "__main__":
    main()
