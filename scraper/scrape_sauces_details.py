# -*- coding: utf-8 -*-
"""Stage 2 of the sauces pipeline: visit each candidate's product detail
page and parse out price and the nutrition-facts panel. Same parsing
logic as scrape_grabgo_details.py (duplicated rather than shared, matching
this project's existing one-script-per-pipeline-stage convention)."""
import json
import re
import time
import urllib.request
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected
from map_ingredients import find_refs_in_text
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
IN_PATH = Path(__file__).parent / "sauces_candidates_raw.json"
OUT_PATH = Path(__file__).parent / "sauces_details_raw.json"


def fetch_off_data(ean):
    """Fallback for products whose K-Ruoka page didn't yield a parseable
    nutrition panel and/or ingredients list (missing entirely, or a
    transient render/click timing miss during a long bulk run) -- Open
    Food Facts is a free, open, barcode-keyed product database with
    strong coverage of products sold in Finland, so it catches real
    products that would otherwise be silently excluded from consideration
    for reasons that have nothing to do with whether they're actually a
    good choice. Fetches both in one call since either can independently
    be missing from K-Ruoka's own page."""
    try:
        url = (f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
               f"?fields=nutriments,ingredients_text_fi,ingredients_text")
        req = urllib.request.Request(url, headers={"User-Agent": "TuoreApp/1.0 (personal recipe app)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        if data.get("status") != 1:
            return None, None
        product = data.get("product", {})
        n = product.get("nutriments", {})
        kcal = n.get("energy-kcal_100g")
        nutrition = None
        if kcal is not None:
            nutrition = {
                'kcal100': kcal,
                'fat100': n.get('fat_100g'),
                'fatSat100': n.get('saturated-fat_100g'),
                'carbs100': n.get('carbohydrates_100g'),
                'sugar100': n.get('sugars_100g'),
                'fiber100': n.get('fiber_100g'),
                'protein100': n.get('proteins_100g'),
                'salt100': n.get('salt_100g'),
            }
        ingredients = product.get('ingredients_text_fi') or product.get('ingredients_text') or None
        return nutrition, ingredients
    except Exception:
        return None, None


def fi_num(s):
    return float(s.replace(',', '.').replace(' ', ''))


def parse_price(text):
    m = re.search(r'Normaalihinta\s*([\d,]+)\s*€\s*(kappale|kilogramma|litra)', text)
    if not m:
        m = re.search(r'Ilman Plussa-korttia\s*([\d,]+)\s*€\s*(kappale|kilogramma|litra)', text)
    if not m:
        m = re.search(r'Hinta\s*(?:noin\s*)?([\d,]+)\s*€\s*(kappale|kilogramma|litra)', text)
    price = fi_num(m.group(1)) if m else None
    unit = m.group(2) if m else None
    um = re.search(r'Yksikköhinta\s*([\d,]+)\s*€\s*(kilogramma|litra|kappale)', text)
    unit_price = fi_num(um.group(1)) if um else None
    unit_price_unit = um.group(2) if um else None
    on_sale = 'Etuhinta' in text
    return price, unit, unit_price, unit_price_unit, on_sale


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
    fat = grab(r'(?<!tyydyttynyttä\t)Rasva\s*([\d,]+)\s*g')
    fat_sat = grab(r'josta tyydyttynyttä\s*([\d,]+)\s*g')
    carbs = grab(r'Hiilihydraatit\s*([\d,]+)\s*g')
    sugar = grab(r'josta sokereita\s*([\d,]+)\s*g')
    fiber = grab(r'Ravintokuitu\s*([\d,]+)\s*g')
    protein = grab(r'Proteiini\s*([\d,]+)\s*g')
    salt = grab(r'Suola\s*([\d,]+)\s*g')
    if kcal is None:
        return None
    return {
        'kcal100': kcal, 'fat100': fat, 'fatSat100': fat_sat, 'carbs100': carbs,
        'sugar100': sugar, 'fiber100': fiber, 'protein100': protein, 'salt100': salt,
    }


def parse_ingredients_text(text):
    """The full ingredients list ('Ainesosat') lives under the separate
    'Tuotetiedot' accordion, not under 'Ravintosisältö' -- confirmed live:
    e.g. a mayo's text reads '...Ainesosat\\n\\nvesi, rypsiöljy, etikka,
    ...\\n\\nAllergeenit...'. Used downstream to detect which of our
    tracked ingredients a product actually contains, for the dislikes
    filter (see map_ingredients.find_refs_in_text)."""
    idx = text.find('Ainesosat')
    if idx == -1:
        return None
    block = text[idx + len('Ainesosat'):idx + len('Ainesosat') + 1500]
    end = len(block)
    for marker in ('Allergeenit', 'E-koodit', 'Alkuperämaa', 'Ravintosisältö'):
        m = block.find(marker)
        if m != -1:
            end = min(end, m)
    ingredients = block[:end].strip()
    return ingredients or None


DIET_KEYWORDS = ['Laktoositon', 'Gluteeniton', 'Vegaaninen', 'Maidoton', 'Soijaton',
                  'Vähälaktoosinen', 'Kasvisruoka']


def parse_diet_tags(text):
    idx = text.find('Ravitsemukselliset ominaisuudet')
    if idx == -1:
        return []
    block = text[idx:idx + 300]
    return [kw for kw in DIET_KEYWORDS if kw in block]


def parse_category(text):
    anchor = 'Ohje\nTuotteet\n'
    idx = text.find(anchor)
    if idx == -1:
        return None, None
    rest = text[idx + len(anchor):]
    lines = [l for l in rest.split('\n') if l.strip()][:2]
    top = lines[0] if len(lines) > 0 else None
    sub = lines[1] if len(lines) > 1 else None
    return top, sub


def main():
    candidates = json.load(open(IN_PATH, encoding="utf-8"))
    print(f"Loaded {len(candidates)} candidates")

    chrome_proc = launch_chrome()
    results = []
    failed = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            ensure_store_selected(page)

            for i, cand in enumerate(candidates, 1):
                ean = cand['ean']
                try:
                    page.goto(f"https://www.k-ruoka.fi/kauppa/tuote/x-{ean}",
                              wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(700)
                    try:
                        page.get_by_text("Ravintosisältö", exact=True).first.click(timeout=4000)
                        page.wait_for_timeout(500)
                    except Exception:
                        pass
                    try:
                        page.get_by_text("Tuotetiedot", exact=True).first.click(timeout=3000)
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
                    text = page.inner_text("body")
                except Exception as e:
                    failed.append({'ean': ean, 'name': cand.get('name'), 'error': str(e)})
                    continue

                price, unit, unit_price, unit_price_unit, on_sale = parse_price(text)
                nutrition = parse_nutrition(text)
                ingredients_text = parse_ingredients_text(text)
                off_fallback_used = False
                if not nutrition or not ingredients_text:
                    off_nutrition, off_ingredients = fetch_off_data(ean)
                    if not nutrition and off_nutrition:
                        nutrition = off_nutrition
                        off_fallback_used = True
                    if not ingredients_text and off_ingredients:
                        ingredients_text = off_ingredients
                    time.sleep(0.3)
                diet_tags = parse_diet_tags(text)
                top_cat, sub_cat = parse_category(text)

                row = dict(cand)
                row['topCategory'] = top_cat
                row['subCategory'] = sub_cat
                row['detailPrice'] = price
                row['detailUnit'] = unit
                row['unitPrice'] = unit_price if unit_price is not None else row.get('unitPrice')
                row['unitPriceUnit'] = unit_price_unit
                row['onSale'] = on_sale
                row['nutrition'] = nutrition
                row['nutritionSource'] = 'openfoodfacts' if off_fallback_used else ('kruoka' if nutrition else None)
                row['ingredientsText'] = ingredients_text
                row['containsRefs'] = find_refs_in_text(ingredients_text) if ingredients_text else []
                row['dietTags'] = diet_tags
                results.append(row)

                if i % 10 == 0:
                    off_count = sum(1 for r in results if r.get('nutritionSource') == 'openfoodfacts')
                    print(f"  {i}/{len(candidates)} done ({sum(1 for r in results if r['nutrition'])} with nutrition, {off_count} via OFF fallback)")

            off_total = sum(1 for r in results if r.get('nutritionSource') == 'openfoodfacts')
            print(f"\nDone. {len(results)} processed, {len(failed)} failed, "
                  f"{sum(1 for r in results if r['nutrition'])} with nutrition data "
                  f"({off_total} via Open Food Facts fallback)")
            json.dump(results, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(failed, open(Path(__file__).parent / "sauces_failed.json", "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()
