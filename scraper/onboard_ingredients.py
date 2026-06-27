# -*- coding: utf-8 -*-
"""Adds brand-new ingredient concepts to the shared ingredient list every
recipe pipeline draws from (recipe_lib.py's FRAC/TITLE/PROTEIN_G/CARB_G/FAT_G
tables, index.html's P dict, and data/canon_map.py's English-phrase mapping).

Run this whenever a new recipe source surfaces ingredients canon_map.py
doesn't recognize (its TO_NEW bucket, or text canon() returns None for).
Only auto-includes a candidate when the store search returns a *confident*
match (same bar add_ingredients.py always required) -- a wrong product or
macro estimate here would silently corrupt every recipe that ends up using
it, so an uncertain match is reported, never guessed.

This script only SEARCHES and COMPUTES; it does not edit recipe_lib.py or
canon_map.py itself (those are hand-reviewed edits applied from its report --
see ONBOARDING.md / the pattern in build_airfryer_recipes.py's comments).
It DOES write the new P dict line into index.html directly, the same way
patch_p_dict.py already does for refreshes."""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scraper import launch_chrome, ensure_store_selected, raw_search, pick_best_match
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
HTML_PATH = Path(__file__).parent.parent / "index.html"
REPORT_PATH = Path(__file__).parent / "onboarded_ingredients.json"

# fraction-of-a-kilogram (or of a single piece) the recipe is *charged for*
# at checkout, by role -- mirrors FRAC's existing role-shaped values
# (e.g. oliveoil=0.1 of a 500ml bottle), used only for pricing.
DEFAULT_FRAC_BY_ROLE = {
    'protein': 1.0, 'vegetable': 0.5, 'herb_spice': 0.1, 'aromatic': 0.5,
    'dairy': 0.2, 'finishing': 0.1, 'carb': 0.4, 'fruit': 0.5,
}

# realistic eating-portion grams per recipe serving, by role -- decoupled
# from FRAC on purpose: checked against existing entries (e.g. oliveoil's
# FAT_G=13 implies ~14g actually eaten, i.e. one tablespoon, even though
# FRAC charges the recipe for 10% of a 500g bottle for pricing/waste
# allowance) -- using FRAC*pack_grams here would overstate macros ~4x
TYPICAL_SERVING_GRAMS_BY_ROLE = {
    'protein': 120, 'vegetable': 100, 'herb_spice': 3, 'aromatic': 15,
    'dairy': 30, 'finishing': 14, 'carb': 60, 'fruit': 80,
}


def fi_num(s):
    return float(s.replace(',', '.').replace(' ', ''))


def parse_nutrition(text):
    idx = text.find('Ravintosisältö')
    if idx == -1:
        return None
    block = text[idx:idx + 700]
    if 'Energia' not in block:
        return None

    def grab(pattern):
        m = re.search(pattern, block)
        return fi_num(m.group(1)) if m else None

    kcal = grab(r'Energia\s*[\d\s]+kJ\s*/\s*([\d,]+)\s*kcal')
    protein = grab(r'Proteiini\s*([\d,]+)\s*g')
    carbs = grab(r'Hiilihydraatit\s*([\d,]+)\s*g')
    fat = grab(r'(?<!tyydyttynyttä\t)Rasva\s*([\d,]+)\s*g')
    if kcal is None or protein is None:
        return None
    return {'kcal100': kcal, 'protein100': protein, 'carbs100': carbs or 0, 'fat100': fat or 0}


def fetch_off_nutrition(ean):
    try:
        url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json?fields=nutriments"
        req = urllib.request.Request(url, headers={"User-Agent": "TuoreApp/1.0 (personal recipe app)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("status") != 1:
            return None
        n = data.get("product", {}).get("nutriments", {})
        kcal = n.get("energy-kcal_100g")
        if kcal is None:
            return None
        return {'kcal100': kcal, 'protein100': n.get('proteins_100g') or 0,
                'carbs100': n.get('carbohydrates_100g') or 0, 'fat100': n.get('fat_100g') or 0}
    except Exception:
        return None


def js_field(name, value):
    if isinstance(value, bool):
        return f'"{name}": {"true" if value else "false"}'
    if isinstance(value, (int, float)):
        return f'"{name}": {value}'
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{name}": "{escaped}"'


def insert_p_dict_entries(added):
    if not added:
        return 0
    html = HTML_PATH.read_text(encoding="utf-8")
    start_marker = "\nconst P={\n"
    end_marker = "\n};\n"
    assert html.count(start_marker) == 1
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    body = html[start:end]

    existing_keys = set(re.findall(r"^(\w+):\{", body, re.MULTILINE))
    already_present = [c['key'] for c in added if c['key'] in existing_keys]
    added = [c for c in added if c['key'] not in existing_keys]
    if already_present:
        print(f"Already in P dict, skipping re-insert: {already_present}")
    if not added:
        return 0

    new_lines = []
    for c in added:
        m = c['match']
        parts = [js_field('nm', c['nm']), js_field('ic', c['icon']),
                  js_field('product', m['name']), js_field('price', m['price']),
                  js_field('unit', m['unit']), js_field('inStock', bool(m['inStockAtStore'])),
                  js_field('ean', m['ean'])]
        new_lines.append(c['key'] + ':{' + ', '.join(parts) + '},')

    body_out = body.rstrip()
    if not body_out.endswith(','):
        body_out += ','
    body_out += '\n' + '\n'.join(new_lines)
    html_out = html[:start] + body_out + html[end:]
    HTML_PATH.write_text(html_out, encoding="utf-8")
    return len(new_lines)


def onboard(candidates):
    """candidates: list of {key, nm, icon, role, search, include, exclude, phrases}.
    phrases = the English ingredient phrases (from canon_map.py's TO_NEW or
    unmatched text) this key should resolve from once promoted to TO_EXISTING."""
    chrome_proc = launch_chrome()
    added, skipped = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for c in candidates:
                results = raw_search(page, c['search'])
                match, confident = pick_best_match(results, c['include'], c['exclude'])
                if not match or not confident:
                    skipped.append({**c, 'reason': 'no confident match',
                                     'bestGuess': match['name'] if match else None})
                    continue
                if not match.get('ean') or match.get('price') is None or not match.get('unit'):
                    skipped.append({**c, 'reason': 'match missing price/unit/ean', 'match': match['name']})
                    continue

                page.goto(f"https://www.k-ruoka.fi/kauppa/tuote/x-{match['ean']}",
                          wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(700)
                try:
                    page.get_by_text("Ravintosisältö", exact=True).first.click(timeout=4000)
                    page.wait_for_timeout(500)
                except Exception:
                    pass
                text = page.inner_text("body")
                nutrition = parse_nutrition(text) or fetch_off_nutrition(match['ean'])
                if not nutrition:
                    skipped.append({**c, 'reason': 'no nutrition data (K-Ruoka or Open Food Facts)',
                                     'match': match['name']})
                    continue

                frac = DEFAULT_FRAC_BY_ROLE.get(c['role'], 0.3)
                serving_grams = TYPICAL_SERVING_GRAMS_BY_ROLE.get(c['role'], 60)
                scale = serving_grams / 100

                added.append({
                    **c, 'match': match, 'frac': frac,
                    'protein_g': round(nutrition['protein100'] * scale, 1),
                    'carbs_g': round(nutrition['carbs100'] * scale, 1),
                    'fat_g': round(nutrition['fat100'] * scale, 1),
                    'nutrition100': nutrition,
                })
                time.sleep(0.5)
    finally:
        chrome_proc.terminate()

    n_inserted = insert_p_dict_entries(added)

    print(f"\nAdded {len(added)} new ingredient(s) to index.html's P dict, skipped {len(skipped)}\n")
    for a in added:
        print(f"  {a['key']:16s} -> {a['match']['name']} (€{a['match']['price']}/{a['match']['unit']})")
        print(f"    FRAC['{a['key']}'] = {a['frac']}")
        print(f"    TITLE['{a['key']}'] = '{a['nm'].lower()}'")
        print(f"    PROTEIN_G['{a['key']}'] = {a['protein_g']}   CARB_G['{a['key']}'] = {a['carbs_g']}"
              f"   FAT_G['{a['key']}'] = {a['fat_g']}")
        print(f"    canon_map.py TO_EXISTING: " + ', '.join(f"'{ph}':'{a['key']}'" for ph in a['phrases']))
    if skipped:
        print("\nSkipped (no confident match -- needs a human look):")
        for s in skipped:
            print(f"  {s['key']:16s} reason: {s['reason']} (best guess: {s.get('bestGuess') or s.get('match')})")

    json.dump({'added': added, 'skipped': skipped}, open(REPORT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nFull report saved to {REPORT_PATH}")
    print("NOTE: recipe_lib.py and data/canon_map.py are NOT auto-edited -- apply the lines above by hand "
          "(or have Claude do it from this report) after a quick sanity check of the matched product.")
    return added, skipped


if __name__ == "__main__":
    print("Import this module and call onboard(candidates) with your candidate list -- "
          "see build_airfryer_recipes.py's missing-ingredient report for the pattern.")
