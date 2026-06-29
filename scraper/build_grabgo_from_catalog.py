# -*- coding: utf-8 -*-
"""One-off: builds a much larger Grab & Go selection from the full catalog
nutrition snapshot (full_catalog_raw.json, 7,266 products / 5,668 with
nutrition) rather than the narrow per-term search the regular weekly
pipeline uses -- the catalog covers the whole store, so this surfaces far
more genuinely healthy ready-to-eat options than a handful of curated
search terms ever could.

Restricted to the 5 top-level K-Ruoka categories that are realistically
"ready to eat without cooking" (fruit/veg, dairy & eggs, bread & crackers,
candy & snacks, ready meals) -- raw meat/fish, dry baking ingredients,
spices, oils and frozen goods are excluded outright since they need real
prep, not because of any finer-grained taxonomy.

health_score is the same formula build_grabgo.py already uses (protein and
fiber positive, sugar/saturated fat/salt negative), with one fix: some
"sugar-free" candy reports 50-90g of "fiber" per 100g because EU labeling
counts bulking agents like polydextrose/maltitol as dietary fiber, which
let several candies outscore actual whole-grain crispbread in testing.
Detected via their ingredient list and excluded from the fiber bonus.

Maps each item onto the small set of `group` keys the frontend's
GRABGO_SECTIONS already knows how to render (any other value would
silently not appear in the UI) -- this is a mechanical category->group
lookup, not a new taxonomy."""
import json
import re
import sys
from pathlib import Path
from statistics import median

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from map_ingredients import find_refs_in_text

IN_PATH = SCRAPER_DIR / "full_catalog_raw.json"
OUT_PATH = SCRAPER_DIR / "grabgo_recommendations.json"

CATEGORY_TO_GROUP = {
    'hedelmat-ja-vihannekset': 'fresh_fruit',
    'maito-juusto-munat-ja-rasvat': 'dairy_snack',
    'leivat-keksit-ja-leivonnaiset': 'healthy_snacks',
    'makeiset-ja-naposteltavat': 'healthy_snacks',
    'valmisruoka': 'ready_meals',
}
GROUP_LABELS = {
    'fresh_fruit': 'Fresh fruit', 'dairy_snack': 'Yogurt & dairy snacks',
    'ready_meals': 'Ready meals', 'healthy_snacks': 'Healthy snacks',
}
GROUP_ICON = {
    'fresh_fruit': 'ti-apple', 'dairy_snack': 'ti-bowl',
    'ready_meals': 'ti-meat', 'healthy_snacks': 'ti-coffee',
}
NEEDS_HEATING_GROUPS = {'ready_meals'}

# EU nutrition labeling counts these bulking/sweetening agents as dietary
# fiber even though they don't behave like real whole-food fiber -- a
# clear sign of a reformulated "diet" candy rather than something the
# fiber bonus was meant to reward.
BULKING_AGENT_MARKERS = ['polydextrose', 'polydekstroosi', 'isomalto', 'maltitol',
                          'oligofructo', 'oligofruktoosi', 'inuliini', 'inulin']

HEALTH_SCORE_THRESHOLD = 0


def is_fake_fiber(item):
    txt = (item.get('ingredientsText') or '').lower()
    return any(m in txt for m in BULKING_AGENT_MARKERS)


def health_score(item):
    n = item['nutrition']
    fiber = 0 if is_fake_fiber(item) else (n.get('fiber100') or 0)
    return (2 * (n.get('protein100') or 0) + 3 * fiber
            - 1.5 * (n.get('sugar100') or 0) - 2 * (n.get('fatSat100') or 0)
            - 6 * (n.get('salt100') or 0))


def percentile_rank(value, all_values, lower_is_better=False):
    if not all_values:
        return 50
    sorted_vals = sorted(all_values, reverse=lower_is_better)
    better_count = sum(1 for v in sorted_vals if (v <= value if lower_is_better else v >= value))
    return round(100 * (1 - better_count / len(sorted_vals)) + 100 / len(sorted_vals))


def has_balanced_brackets(text):
    return all(text.count(o) == text.count(c) for o, c in [('(', ')'), ('[', ']'), ('{', '}')])


def name_root(name):
    stripped = re.sub(r'\d+\s*(g|kg|ml|l|kpl).*$', '', name.lower())
    return tuple(stripped.split()[0:3])


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))

    pool = [d for d in data if d.get('categorySlug') in CATEGORY_TO_GROUP
            and d.get('nutrition') and d.get('price') is not None and d.get('unitPrice')]
    print(f"{len(pool)} candidates have a usable category, nutrition, and price")

    for item in pool:
        item['_health'] = health_score(item)

    # dedup: same brand + first few name words (after stripping pack size)
    # is almost always just a different pack size of the same product --
    # keep only the best-scoring one so the list reads as varied rather
    # than padded with near-duplicates.
    pool.sort(key=lambda i: -i['_health'])
    seen = set()
    deduped = []
    for item in pool:
        key = (item.get('brand'), name_root(item['name']))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    print(f"{len(deduped)} after dedup by brand+name-root")

    qualifying = [i for i in deduped if i['_health'] >= HEALTH_SCORE_THRESHOLD]
    print(f"{len(qualifying)} qualify at health_score >= {HEALTH_SCORE_THRESHOLD}")

    health_scores = [i['_health'] for i in qualifying]
    prices = [i['unitPrice'] for i in qualifying]
    for item in qualifying:
        item['_healthPct'] = percentile_rank(item['_health'], health_scores)
        item['_valuePct'] = percentile_rank(item['unitPrice'], prices, lower_is_better=True)

    recommendations = []
    for item in qualifying:
        n = item['nutrition']
        group = CATEGORY_TO_GROUP[item['categorySlug']]
        all_refs = set(find_refs_in_text(item['name']))
        if item.get('ingredientsText'):
            all_refs |= set(find_refs_in_text(item['ingredientsText']))

        # some source ingredient lists have mismatched brackets (messy
        # upstream data, e.g. nested [..] inside (..)) -- the naive
        # whole-file brace-balance check in validate_index.py can't tell
        # that from a real syntax break, so drop the text rather than
        # risk it; the UI already falls back gracefully when this is null
        ingredients_text = item.get('ingredientsText')
        if ingredients_text and not has_balanced_brackets(ingredients_text):
            ingredients_text = None

        badges = []
        if item['_healthPct'] >= 75:
            badges.append('Healthy pick')
        if item['_valuePct'] >= 75 and len(badges) < 2:
            badges.append('Great value')
        if (n.get('protein100') or 0) >= 12 and len(badges) < 2:
            badges.append('High protein')
        if (n.get('sugar100') or 0) <= 3 and len(badges) < 2:
            badges.append('Low sugar')
        if not badges:
            badges.append('Worth a look')

        recommendations.append({
            'ean': item['ean'], 'name': item['name'], 'brand': item.get('brand'),
            'group': group, 'groupLabel': GROUP_LABELS[group], 'icon': GROUP_ICON[group],
            'price': item['price'], 'unit': item.get('unit'),
            'unitPrice': item.get('unitPrice'), 'unitPriceUnit': item.get('unitPriceUnit'),
            'onSale': False,
            'kcal100': n.get('kcal100'), 'protein100': n.get('protein100'),
            'carbs100': n.get('carbs100'), 'sugar100': n.get('sugar100'),
            'fiber100': n.get('fiber100'), 'fat100': n.get('fat100'),
            'fatSat100': n.get('fatSat100'), 'salt100': n.get('salt100'),
            'dietTags': [],
            'badges': badges[:2],
            'needsHeating': group in NEEDS_HEATING_GROUPS,
            'isWholeProduce': False,
            'healthPct': item['_healthPct'], 'valuePct': item['_valuePct'],
            'containsRefs': sorted(all_refs),
            'ingredientsText': ingredients_text,
        })

    print(f"\nFinal recommendation count: {len(recommendations)}")
    from collections import Counter
    print('by group:', dict(Counter(r['group'] for r in recommendations)))

    json.dump(recommendations, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
