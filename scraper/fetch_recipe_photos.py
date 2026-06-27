# -*- coding: utf-8 -*-
"""Fetches a relevant stock photo from Unsplash for any recipe lacking one
(no real photo from K-Ruoka's own catalog). Run this manually, once, right
after adding new recipes -- deliberately NOT wired into any cron-scheduled
refresh job, since Unsplash's API guidelines call for "non-automated, high-
quality, and authentic experiences"; one search per real new recipe, run
because a person asked for it, fits that, while a recurring background job
that bulk-fetches photos on a timer would not.

Free tier is 50 requests/hour, so this comfortably handles a batch of new
recipes at a time. Stores photographer credit alongside the URL -- required
by Unsplash's API terms whenever a photo is displayed."""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

KEY_PATH = Path(__file__).parent / "keys" / "unsplash_access_key.txt"
HTML_PATH = Path(__file__).parent.parent / "index.html"
OUT_PATH = Path(__file__).parent / "recipe_stock_photos.json"

STRIP_WORDS = {'air', 'fryer', 'air-fryer', 'recipe', 'with', 'and', '&', 'the'}


def search_query_for(name):
    words = re.sub(r'[^\w\s-]', ' ', name.lower()).split()
    kept = [w for w in words if w not in STRIP_WORDS]
    return ' '.join(kept) or name


def fetch_photo(key, query):
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode({
        'query': query, 'per_page': 1, 'orientation': 'landscape',
    })
    req = urllib.request.Request(url, headers={'Authorization': f'Client-ID {key}', 'Accept-Version': 'v1'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    results = data.get('results') or []
    if not results:
        return None
    r = results[0]
    return {
        'url': r['urls']['regular'],
        'photographer': r['user']['name'],
        'photographerUrl': r['user']['links']['html'] + '?utm_source=tuore&utm_medium=referral',
        'downloadLocation': r['links']['download_location'],
        'query': query,
    }


def find_meal_ids_missing_photo(target_ids=None):
    html = HTML_PATH.read_text(encoding="utf-8")
    meals_block = html[html.index("\nlet meals=["):html.index("\n];\n", html.index("\nlet meals=["))]
    out = []
    for line in meals_block.split('\n'):
        m = re.match(r"\{id:'([^']+)',name:\"([^\"]*)\"", line)
        if not m:
            continue
        mid, name = m.groups()
        if target_ids is not None and mid not in target_ids:
            continue
        if "photo:'" in line or '"stockPhoto"' in line or 'stockPhoto:' in line:
            continue
        out.append((mid, name))
    return out


def main(target_ids=None):
    if not KEY_PATH.exists():
        print(f"No Unsplash key found at {KEY_PATH}")
        sys.exit(1)
    key = KEY_PATH.read_text(encoding="utf-8").strip()

    todo = find_meal_ids_missing_photo(target_ids)
    print(f"{len(todo)} recipes need a photo")
    if not todo:
        return

    existing = json.load(open(OUT_PATH, encoding="utf-8")) if OUT_PATH.exists() else {}
    for mid, name in todo:
        query = search_query_for(name)
        try:
            photo = fetch_photo(key, query)
        except Exception as e:
            print(f"  FAILED  {mid}  ({query!r}): {e}")
            continue
        if not photo:
            print(f"  no result  {mid}  ({query!r})")
            continue
        existing[mid] = photo
        print(f"  OK  {mid}  -> {photo['photographer']} ({query!r})")

    json.dump(existing, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
