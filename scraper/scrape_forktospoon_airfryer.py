# -*- coding: utf-8 -*-
"""Crawls Fork To Spoon's air-fryer category (a much larger, dedicated
air-fryer recipe site -- ~105 pages, vs. Budget Bytes' 27 total air-fryer
recipes) for recipe URLs, then fetches each recipe's own Recipe JSON-LD --
name, real ingredients, real nutrition (including sodium and saturated
fat, which Budget Bytes' schema didn't expose), real time, url.

Note: this site's recipes carry no aggregateRating at all (confirmed by
sampling several pages before writing this) -- unlike the Budget Bytes
pipelines, there is no review-count/rating gate available here. Health
filtering for this batch leans on the richer nutrition fields instead
(see build_forktospoon_recipes.py).

Plain HTTP only, no Chrome/CDP: forktospoon.com carries no Cloudflare bot
protection, so this never needs the real-Chrome trick or the VM -- runs
entirely locally, independent of whatever scrape is running on the
Oracle VM at the same time.

Resumable: skips any URL already in this file's own output."""
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# real scraped titles can carry characters (zero-width spaces, smart
# quotes, etc.) outside Windows' default cp1252 console/file encoding --
# without this, print() on an affected title crashes the whole script
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CATEGORY_URL = "https://forktospoon.com/method/air-fryer/page/{}/"
MAX_PAGES = 120
OUT_PATH = Path(__file__).parent / "forktospoon_airfryer_raw.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TuoreApp-research/1.0 (personal recipe app)"
CHECKPOINT_EVERY = 25

LINK_RE = re.compile(r'href="(https://forktospoon\.com/[a-z0-9-]+/)"')
SKIP_PATH_PARTS = (
    '/method/', '/page/', '/category/', '/feed', '/wp-', '/comments/', 'xmlrpc',
    '/about/', '/cookbook/', '/contact/', '/privacy-policy/', '/terms/',
    '/weekly-meal-plan', '/air-fryer-cooking-chart/',
)


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def discover_recipe_urls():
    urls = []
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        url = CATEGORY_URL.format(page)
        try:
            html = fetch(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  page {page}: 404 -- end of pagination")
                break
            print(f"  page {page}: HTTP {e.code}, skipping")
            continue
        except Exception as e:
            print(f"  page {page}: error {e}, skipping")
            continue

        found = set(LINK_RE.findall(html))
        new_this_page = 0
        for u in found:
            if any(part in u for part in SKIP_PATH_PARTS):
                continue
            if u not in seen:
                seen.add(u)
                urls.append(u)
                new_this_page += 1
        print(f"  page {page}: {new_this_page} new links ({len(urls)} total so far)")
        time.sleep(0.4 + random.uniform(0, 0.4))
    return urls


def extract_recipe_jsonld(html):
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for c in list(candidates):
            if isinstance(c, dict) and "@graph" in c:
                candidates = candidates + c["@graph"]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            t = c.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Recipe" in types:
                return c
    return None


def fetch_recipe(url):
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  FAILED {url}: {e}")
        return None
    recipe = extract_recipe_jsonld(html)
    if not recipe:
        print(f"  no Recipe schema (probably a roundup/info page): {url}")
        return None
    return {"recipe": recipe, "url": url}


def main():
    out = []
    done_urls = set()
    if OUT_PATH.exists():
        out = json.load(open(OUT_PATH, encoding="utf-8"))
        done_urls = {d["url"] for d in out}
        print(f"Resuming: {len(out)} recipes already scraped")

    print("Discovering recipe URLs from the air-fryer category...")
    all_urls = discover_recipe_urls()
    todo = [u for u in all_urls if u not in done_urls]
    print(f"\n{len(all_urls)} unique URLs found, {len(todo)} new to fetch\n")

    for i, url in enumerate(todo, 1):
        d = fetch_recipe(url)
        if d:
            out.append(d)
            print(f"  [{i}/{len(todo)}] {d['recipe'].get('name', '?')}")
        if i % CHECKPOINT_EVERY == 0:
            json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  checkpoint saved ({len(out)} total)")
        time.sleep(0.4 + random.uniform(0, 0.5))

    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nDone. {len(out)} total recipes saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
