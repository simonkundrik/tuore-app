# -*- coding: utf-8 -*-
"""Builds the Grab & Go selection from the full catalog nutrition snapshot
(full_catalog_raw.json, 7,266 products / 5,668 with nutrition) rather than
the narrow per-term search the old pipeline used -- the catalog covers the
whole store, so this surfaces far more genuinely useful ready-to-eat
options than a handful of curated search terms ever could.

Restricted to the 5 top-level K-Ruoka categories that are realistically
"ready to eat without cooking" (fruit/veg, dairy & eggs, bread & crackers,
candy & snacks, ready meals) -- raw meat/fish, dry baking ingredients,
spices, oils and frozen goods are excluded outright since they need real
prep, not because of any finer-grained taxonomy. Each is further split into
a richer set of `group`s (fresh fruit / vegetables & herbs / dairy /
bakery / sweets / crisps / nuts / savory bites / ready meals) so the UI
can show distinct browsable sections instead of one big bucket.

health_score rewards protein/fiber and penalizes sugar/saturated fat/salt
(same formula as the old build_grabgo.py), with one fix: some "sugar-free"
candy reports 50-90g of "fiber" per 100g because EU labeling counts
bulking agents like polydextrose/maltitol as dietary fiber, which let
several candies outscore actual whole-grain crispbread in testing.
Detected via their ingredient list and excluded from the fiber bonus.

For 'sweets', 'crisps' and 'bakery' specifically, health_score alone
would exclude almost everything -- a treat is a treat. Real feedback:
dieting is about compromise, not all-or-nothing purity, so a lower-calorie
option within an indulgent category is a legitimate, useful recommendation
even when its protein/fiber profile doesn't justify a positive
health_score on its own. Those groups additionally qualify anything
notably lower-calorie than is typical for that category (thresholds
picked from the live calorie distribution: sweets/bakery median
~400kcal/100g, crisps median ~517kcal/100g)."""
import json
import re
import sys
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR))
from map_ingredients import find_refs_in_text

IN_PATH = SCRAPER_DIR / "full_catalog_raw.json"
OUT_PATH = SCRAPER_DIR / "grabgo_recommendations.json"

VEG_KEYWORDS = ['tomaat', 'kurkku', 'paprika', 'salaatti', 'parsa', 'kaali', 'herne',
                'papu', 'pinaatti', 'basilik', 'persilj', 'tilli', 'korianter', 'mintt',
                'rosmariin', 'timjam', 'oregano', 'salvia', 'ruohosipul', 'laventel',
                'melissa', 'inkivä', 'fenkoli', 'sien', 'avokado', 'bataatti', 'chili',
                'peruna', 'sipuli', 'porkkana', 'retiis', 'palsternak']
CRISPS_KEYWORDS = ['sipsi', 'chips', 'pringles', 'popcorn', 'snacks', 'snack',
                    'perunalastu', 'crisp']
NUTS_KEYWORDS = ['pähkin', 'manteli', 'cashew', 'pistaasi', 'siemen', 'nut']

JERKY_KEYWORDS = ['jerky', 'biltong', 'kuivaliha', 'palvattu']
# fruit bars are a sweet treat, not a crisp -- needed since "hedelmäpatukka"
# kept losing to the generic 'snack' crisps keyword whenever a product's
# own brand name happened to contain "Snack" (e.g. "MySnack Mango
# hedelmäpatukka") and it had no real category path to override that
FRUIT_BAR_KEYWORDS = ['hedelmäpatukka', 'hedelmäpatukat']
DIP_MIX_KEYWORDS = ['dipmix', 'dippimix', 'dippimauste', 'dippi']
# last-resort check right before something would default to 'sweets':
# any clearly savory flavor word means it's not actually a treat, even
# if it didn't match dip-mix or nuts already.
SAVORY_FLAVOR_RESCUE = ['juusto', 'valkosipuli', 'kermaviili', 'cheez', 'cheese']
# frozen items need real cooking regardless of which category they're
# filed under -- not a finer taxonomy question, just out of scope
FROZEN_EXCLUDE = ['pakaste']

# Real feedback: bread/crackers, sweet pastries, cookies, and savory
# bakery-counter pies were scattered across Crackers/Sweets/Savory bites
# depending on whether a given item happened to be sweet or savory -- not
# how a real bakery presents its own range. Now everything K-Ruoka files
# under its own "leivat-keksit-ja-leivonnaiset" (bread/cookies/pastries)
# top category becomes one Bakery section regardless of sweet vs savory,
# which also sidesteps the keyword-guessing this used to need entirely
# (no more separately classifying crackers vs sweets vs savory hand pies
# within that one category -- see classify_group below).
#
# K-Ruoka's own search API returns each product's real subcategory path
# (confirmed live, e.g. "leivat-keksit-ja-leivonnaiset/leivat/tummat-leivat"
# for rye bread) -- backfilled onto full_catalog_raw.json by
# backfill_category_path.py. Used here only for the "needs real home
# baking" exclusion and for makeiset-ja-naposteltavat (candy/snacks),
# which still benefits from precise subcategory-based splitting.
CATEGORY_PATH_EXCLUDE = {
    'leivat-keksit-ja-leivonnaiset/leivat/kotona-paistettavat-leivat',
    'leivat-keksit-ja-leivonnaiset/leivonnaiset/kotona-paistettavat-leivonnaiset',
}
CATEGORY_PATH_GROUP = {
    'makeiset-ja-naposteltavat/karkkipussit/karkkipussit': 'sweets',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/sipsit': 'crisps',
    'makeiset-ja-naposteltavat/suklaat/suklaapatukat': 'sweets',
    'makeiset-ja-naposteltavat/suklaat/suklaalevyt': 'sweets',
    'makeiset-ja-naposteltavat/muut-makeiset/muut-makeiset': 'sweets',
    'makeiset-ja-naposteltavat/muut-makeiset/kausimakeiset': 'sweets',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/snacks-pahkinat': 'nuts',
    'makeiset-ja-naposteltavat/pastillit/karkkipastillit': 'sweets',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/juusto--ja-muotosnacksit': 'savory_snacks',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/muut-snacksit': 'crisps',
    'makeiset-ja-naposteltavat/suklaat/konvehdit': 'sweets',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/dipit': 'savory_snacks',
    'makeiset-ja-naposteltavat/sipsit-ja-snacksit/popcornit': 'crisps',
    'makeiset-ja-naposteltavat/pastillit/kurkkupastillit': 'sweets',
    'makeiset-ja-naposteltavat/purukumit/ksylitoli-isot': 'sweets',
    'makeiset-ja-naposteltavat/pastillit/ksylitolipastillit': 'sweets',
    'makeiset-ja-naposteltavat/karkkipussit/kurkkupastillipussit': 'sweets',
    'makeiset-ja-naposteltavat/purukumit/ksylitoli-pienet': 'sweets',
    'makeiset-ja-naposteltavat/purukumit/muut-purukumit': 'sweets',
}

CATEGORY_GROUPS = {
    'hedelmat-ja-vihannekset', 'maito-juusto-munat-ja-rasvat',
    'leivat-keksit-ja-leivonnaiset', 'makeiset-ja-naposteltavat', 'valmisruoka',
}
GROUP_LABELS = {
    'fresh_fruit': 'Fresh fruit', 'raw_veg': 'Vegetables & herbs',
    'dairy_snack': 'Yogurt & dairy snacks', 'bakery': 'Bakery',
    'sweets': 'Healthy(ish) sweets', 'crisps': 'Crisps & savory snacks',
    'nuts': 'Nuts & seeds', 'savory_snacks': 'Savory bites',
    'ready_meals': 'Ready meals',
}
GROUP_ICON = {
    'fresh_fruit': 'ti-apple', 'raw_veg': 'ti-leaf', 'dairy_snack': 'ti-bowl',
    'bakery': 'ti-bread', 'sweets': 'ti-candy', 'crisps': 'ti-stack',
    'nuts': 'ti-coffee', 'savory_snacks': 'ti-meat', 'ready_meals': 'ti-meat',
}
NEEDS_HEATING_GROUPS = {'ready_meals'}

# groups where health_score alone would exclude almost everything -- a
# notably lower-than-typical calorie count is also a legitimate
# "compromise, not sacrifice" pick on its own. Bakery needs this too now
# that it's a mix of genuinely good whole-grain bread (passes on
# health_score alone) and sweet pastries/cookies (a treat is a treat).
LOW_CAL_THRESHOLD = {'sweets': 350, 'crisps': 450, 'bakery': 350}

# EU nutrition labeling counts these bulking/sweetening agents as dietary
# fiber even though they don't behave like real whole-food fiber -- a
# clear sign of a reformulated "diet" candy rather than something the
# fiber bonus was meant to reward.
BULKING_AGENT_MARKERS = ['polydextrose', 'polydekstroosi', 'isomalto', 'maltitol',
                          'oligofructo', 'oligofruktoosi', 'inuliini', 'inulin']

HEALTH_SCORE_THRESHOLD = 0


def classify_group(item):
    cat = item['categorySlug']
    name_low = item['name'].lower()
    path = item.get('categoryPath')

    if any(k in name_low for k in FROZEN_EXCLUDE):
        return None
    if path in CATEGORY_PATH_EXCLUDE:
        return None
    if any(k in name_low for k in JERKY_KEYWORDS):
        return 'savory_snacks'
    if any(k in name_low for k in FRUIT_BAR_KEYWORDS):
        return 'bakery' if cat == 'leivat-keksit-ja-leivonnaiset' else 'sweets'
    # crisps show up in both the bakery and candy/snacks top categories
    # (e.g. rye crisps are filed under bread) -- checked before the
    # bakery-wide rule below so they stay in crisps rather than bakery
    if cat in ('leivat-keksit-ja-leivonnaiset', 'makeiset-ja-naposteltavat') \
            and any(k in name_low for k in CRISPS_KEYWORDS):
        return 'crisps'
    if cat == 'leivat-keksit-ja-leivonnaiset':
        return 'bakery'

    if path in CATEGORY_PATH_GROUP:
        return CATEGORY_PATH_GROUP[path]
    if cat == 'hedelmat-ja-vihannekset':
        return 'raw_veg' if any(k in name_low for k in VEG_KEYWORDS) else 'fresh_fruit'
    if cat == 'maito-juusto-munat-ja-rasvat':
        return 'dairy_snack'
    if cat == 'valmisruoka':
        return 'ready_meals'
    if cat == 'makeiset-ja-naposteltavat':
        if any(k in name_low for k in DIP_MIX_KEYWORDS):
            return 'savory_snacks'
        if any(k in name_low for k in NUTS_KEYWORDS):
            return 'nuts'
        return 'savory_snacks' if any(k in name_low for k in SAVORY_FLAVOR_RESCUE) else 'sweets'
    return None


def is_fake_fiber(item):
    txt = (item.get('ingredientsText') or '').lower()
    return any(m in txt for m in BULKING_AGENT_MARKERS)


def health_score(item):
    n = item['nutrition']
    fiber = 0 if is_fake_fiber(item) else (n.get('fiber100') or 0)
    return (2 * (n.get('protein100') or 0) + 3 * fiber
            - 1.5 * (n.get('sugar100') or 0) - 2 * (n.get('fatSat100') or 0)
            - 6 * (n.get('salt100') or 0))


def qualifies(item, group):
    if item['_health'] >= HEALTH_SCORE_THRESHOLD:
        return True
    thresh = LOW_CAL_THRESHOLD.get(group)
    if thresh is not None:
        kcal = item['nutrition'].get('kcal100')
        return kcal is not None and kcal <= thresh
    return False


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

    pool = [d for d in data if d.get('categorySlug') in CATEGORY_GROUPS
            and d.get('nutrition') and d.get('price') is not None and d.get('unitPrice')]
    print(f"{len(pool)} candidates have a usable category, nutrition, and price")

    for item in pool:
        item['_group'] = classify_group(item)
        item['_health'] = health_score(item)
    excluded_frozen = sum(1 for i in pool if i['_group'] is None)
    pool = [i for i in pool if i['_group'] is not None]
    if excluded_frozen:
        print(f"Excluded {excluded_frozen} frozen items (need real cooking despite their listed category)")

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

    qualifying = [i for i in deduped if qualifies(i, i['_group'])]
    print(f"{len(qualifying)} qualify (health_score >= {HEALTH_SCORE_THRESHOLD}, "
          f"or notably lower-calorie than typical for sweets/crisps)")

    health_scores = [i['_health'] for i in qualifying]
    prices = [i['unitPrice'] for i in qualifying]
    for item in qualifying:
        item['_healthPct'] = percentile_rank(item['_health'], health_scores)
        item['_valuePct'] = percentile_rank(item['unitPrice'], prices, lower_is_better=True)

    recommendations = []
    for item in qualifying:
        n = item['nutrition']
        group = item['_group']
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
        if item['_health'] >= HEALTH_SCORE_THRESHOLD and item['_healthPct'] >= 75:
            badges.append('Healthy pick')
        elif item['_health'] < HEALTH_SCORE_THRESHOLD:
            badges.append('Lighter choice')
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
            'healthScore': item['_health'],
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
