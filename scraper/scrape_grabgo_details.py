# -*- coding: utf-8 -*-
"""Stage 2 of the grab-and-go pipeline: visit each candidate's product
detail page (just /kauppa/tuote/x-{ean} -- the slug prefix is cosmetic,
the backend resolves on the EAN suffix) and parse out the regular price
and the nutrition-facts panel, which is server-rendered into the page
(no extra XHR needed) but not exposed by any JSON API we could reach."""
import json
import re
import time
from pathlib import Path
from scraper import launch_chrome, ensure_store_selected
from playwright.sync_api import sync_playwright

DEBUG_PORT = 9333
IN_PATH = Path(__file__).parent / "grabgo_candidates_raw.json"
OUT_PATH = Path(__file__).parent / "grabgo_details_raw.json"


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
    if kcal is None or protein is None:
        return None
    return {
        'kcal100': kcal, 'fat100': fat, 'fatSat100': fat_sat, 'carbs100': carbs,
        'sugar100': sugar, 'fiber100': fiber, 'protein100': protein, 'salt100': salt,
    }


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
                        page.get_by_text("Ravintosisältö", exact=True).first.click(timeout=2000)
                        page.wait_for_timeout(300)
                    except Exception:
                        pass  # heading not present -- likely no nutrition panel (e.g. raw produce)
                    text = page.inner_text("body")
                except Exception as e:
                    failed.append({'ean': ean, 'name': cand.get('name'), 'error': str(e)})
                    continue

                price, unit, unit_price, unit_price_unit, on_sale = parse_price(text)
                nutrition = parse_nutrition(text)
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
                row['dietTags'] = diet_tags
                results.append(row)

                if i % 25 == 0:
                    print(f"  {i}/{len(candidates)} done ({sum(1 for r in results if r['nutrition'])} with nutrition)")

            print(f"\nDone. {len(results)} processed, {len(failed)} failed, "
                  f"{sum(1 for r in results if r['nutrition'])} with nutrition data")
            json.dump(results, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(failed, open(Path(__file__).parent / "grabgo_failed.json", "w", encoding="utf-8"), ensure_ascii=False)
            print(f"Saved {OUT_PATH}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()
