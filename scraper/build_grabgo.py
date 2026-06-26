# -*- coding: utf-8 -*-
"""Scores the scraped grab-and-go candidates on health (nutrition-based,
ranked within its own food group so nuts aren't penalized for being
calorie-dense the way a sugary yogurt would be) and value (price vs. the
group's own median), then picks the best of each group.

Whole fresh produce has no nutrition label at K-Ruoka (not legally
required for unprocessed food), so common items get a small hardcoded
reference table -- standard public-domain per-100g facts, not scraped."""
import json
import re
from pathlib import Path
from statistics import median

IN_PATH = Path(__file__).parent / "grabgo_details_raw.json"
OUT_PATH = Path(__file__).parent / "grabgo_recommendations.json"

# name-substring -> per-100g {kcal, protein, carbs, sugar, fiber, fatSat, salt}
# standard reference values (USDA/Fineli-style averages), used only when
# K-Ruoka has no nutrition panel for the item (i.e. whole fresh produce).
PRODUCE_REFERENCE = [
    ('banaani',      dict(kcal100=89,  protein100=1.1, carbs100=23, sugar100=12,  fiber100=2.6, fatSat100=0.1, salt100=0)),
    ('omena',        dict(kcal100=52,  protein100=0.3, carbs100=14, sugar100=10,  fiber100=2.4, fatSat100=0.0, salt100=0)),
    ('appelsiini',   dict(kcal100=47,  protein100=0.9, carbs100=12, sugar100=9,   fiber100=2.4, fatSat100=0.0, salt100=0)),
    ('veriappelsiin', dict(kcal100=47, protein100=0.9, carbs100=12, sugar100=9,   fiber100=2.4, fatSat100=0.0, salt100=0)),
    ('päärynä',      dict(kcal100=57,  protein100=0.4, carbs100=15, sugar100=10,  fiber100=3.1, fatSat100=0.0, salt100=0)),
    ('mandariini',   dict(kcal100=53,  protein100=0.8, carbs100=13, sugar100=10.6, fiber100=1.8, fatSat100=0.0, salt100=0)),
    ('klementiini',  dict(kcal100=47,  protein100=0.9, carbs100=12, sugar100=9,   fiber100=1.7, fatSat100=0.0, salt100=0)),
    ('mango',        dict(kcal100=60,  protein100=0.8, carbs100=15, sugar100=14,  fiber100=1.6, fatSat100=0.1, salt100=0)),
    ('ananas',       dict(kcal100=50,  protein100=0.5, carbs100=13, sugar100=10,  fiber100=1.4, fatSat100=0.0, salt100=0)),
    ('vesimeloni',   dict(kcal100=30,  protein100=0.6, carbs100=8,  sugar100=6,   fiber100=0.4, fatSat100=0.0, salt100=0)),
    ('hunajameloni', dict(kcal100=36,  protein100=0.5, carbs100=9,  sugar100=8,   fiber100=0.8, fatSat100=0.0, salt100=0)),
    ('galiameloni',  dict(kcal100=36,  protein100=0.5, carbs100=9,  sugar100=8,   fiber100=0.8, fatSat100=0.0, salt100=0)),
    ('meloni',       dict(kcal100=34,  protein100=0.6, carbs100=8,  sugar100=7,   fiber100=0.6, fatSat100=0.0, salt100=0)),
    ('rypäle',       dict(kcal100=69,  protein100=0.7, carbs100=18, sugar100=16,  fiber100=0.9, fatSat100=0.1, salt100=0)),
    ('kiivi',        dict(kcal100=61,  protein100=1.1, carbs100=15, sugar100=9,   fiber100=3.0, fatSat100=0.0, salt100=0)),
    ('nektariini',   dict(kcal100=44,  protein100=1.1, carbs100=10, sugar100=8,   fiber100=1.7, fatSat100=0.0, salt100=0)),
    ('persikka',     dict(kcal100=39,  protein100=0.9, carbs100=10, sugar100=8,   fiber100=1.5, fatSat100=0.0, salt100=0)),
    ('aprikoosi',    dict(kcal100=48,  protein100=1.4, carbs100=11, sugar100=9,   fiber100=2.0, fatSat100=0.0, salt100=0)),
    ('paraguayo',    dict(kcal100=39,  protein100=0.9, carbs100=10, sugar100=8,   fiber100=1.5, fatSat100=0.0, salt100=0)),
    ('mansikka',     dict(kcal100=32,  protein100=0.7, carbs100=8,  sugar100=4.9, fiber100=2.0, fatSat100=0.0, salt100=0)),
    ('mustikka',     dict(kcal100=57,  protein100=0.7, carbs100=14, sugar100=10,  fiber100=2.4, fatSat100=0.0, salt100=0)),
    ('vadelma',      dict(kcal100=52,  protein100=1.2, carbs100=12, sugar100=4.4, fiber100=6.5, fatSat100=0.0, salt100=0)),
    ('kurkku',       dict(kcal100=15,  protein100=0.7, carbs100=4,  sugar100=1.7, fiber100=0.5, fatSat100=0.1, salt100=0)),
    ('tomaatti',     dict(kcal100=18,  protein100=0.9, carbs100=4,  sugar100=2.6, fiber100=1.2, fatSat100=0.0, salt100=0)),
    ('paprika',      dict(kcal100=31,  protein100=1.0, carbs100=6,  sugar100=4.2, fiber100=2.1, fatSat100=0.0, salt100=0)),
]

# substrings that mean "this isn't really whole produce" even though it
# matched a fruit/veg search term (juices, purees, frozen, jams, sauces)
PRODUCE_EXCLUDE = ['mehu', 'sose', 'pakaste', 'hillo', 'keitto', 'smoothie', 'kastike',
                    'kivennäisvesi', 'virvoitusjuoma']

# the real K-Ruoka top-level category each group's items must actually
# belong to -- free-text search returns "best match" results that are
# sometimes only loosely related (e.g. a "minipaprika" search surfacing
# paprika-marinated chicken wings), so this is the main defense against
# recommending something that needs real cooking or isn't food at all.
EXPECTED_TOP_CATEGORY = {
    'fresh_fruit': ['Hedelmät ja vihannekset'],
    'berries': ['Hedelmät ja vihannekset'],
    'raw_veg_snack': ['Hedelmät ja vihannekset'],
    'dairy_snack': ['Maito, juusto, munat ja rasvat'],
    'ready_meals': ['Valmisruoka'],
    'ready_salads': ['Valmisruoka'],
    'deli': ['Liha ja kasviproteiinit'],
    'smoked_fish': ['Kala ja merenelävät'],
    'nuts_snacks': ['Makeiset ja naposteltavat'],
    'dips': ['Makeiset ja naposteltavat', 'Valmisruoka', 'Hedelmät ja vihannekset'],
}

# "Makeiset ja naposteltavat" covers candy and chips as well as snack nuts;
# "Valmisruoka" covers fresh pasta as well as dips. Top-category alone
# isn't precise enough for these two groups, so also require/forbid
# specific words in the product name itself.
GROUP_NAME_FILTER = {
    'nuts_snacks': {
        'include_any': ['pähkin', 'manteli', 'cashew', 'pistaasi'],
        'exclude_any': ['suklaa', 'sipsi', 'patukka', 'popcorn', 'lindor', 'lindt'],
    },
    'dips': {
        'include_any': ['hummus', 'guacamole', 'tahini', 'dippi', 'avokado'],
        'exclude_any': ['pasta', 'tortelloni', 'fettuccine', 'ravioli', 'lasagne', 'gnocchi'],
    },
}


def passes_name_filter(group, name):
    f = GROUP_NAME_FILTER.get(group)
    if not f:
        return True
    name_low = name.lower()
    if any(x in name_low for x in f.get('exclude_any', [])):
        return False
    include = f.get('include_any')
    if include and not any(x in name_low for x in include):
        return False
    return True

GROUP_LABELS = {
    'fresh_fruit': 'Fresh fruit', 'berries': 'Berries', 'raw_veg_snack': 'Raw veg',
    'dairy_snack': 'Yogurt & dairy snacks', 'ready_meals': 'Ready meals',
    'ready_salads': 'Ready salads', 'deli': 'Cold cuts & deli',
    'smoked_fish': 'Smoked & cured fish', 'nuts_snacks': 'Nuts', 'dips': 'Dips',
}
NEEDS_HEATING_TERMS = {'mikroateria', 'mikrokeitto', 'pizza', 'kebab', 'hampurilainen', 'hotdog'}
GROUP_ICON = {
    'fresh_fruit': 'ti-apple', 'berries': 'ti-apple', 'raw_veg_snack': 'ti-leaf',
    'dairy_snack': 'ti-bowl', 'ready_meals': 'ti-meat', 'ready_salads': 'ti-leaf',
    'deli': 'ti-meat', 'smoked_fish': 'ti-fish', 'nuts_snacks': 'ti-coffee', 'dips': 'ti-bowl',
}


def attach_produce_reference(row):
    name_low = row['name'].lower()
    if any(x in name_low for x in PRODUCE_EXCLUDE):
        return None
    for keyword, ref in PRODUCE_REFERENCE:
        if keyword in name_low:
            return dict(ref)
    return None


def health_score(n):
    return (2 * n['protein100'] + 3 * (n.get('fiber100') or 0)
            - 1.5 * (n.get('sugar100') or 0) - 2 * (n.get('fatSat100') or 0)
            - 6 * (n.get('salt100') or 0))


def percentile_rank(value, all_values, lower_is_better=False):
    if not all_values:
        return 50
    sorted_vals = sorted(all_values, reverse=lower_is_better)
    better_count = sum(1 for v in sorted_vals if (v <= value if lower_is_better else v >= value))
    return round(100 * (1 - better_count / len(sorted_vals)) + 100 / len(sorted_vals))


def needs_heating(row):
    return row.get('searchTerm') in NEEDS_HEATING_TERMS


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))
    rows = []
    wrong_category = 0
    for r in data:
        expected = EXPECTED_TOP_CATEGORY.get(r.get('group'))
        if expected and r.get('topCategory') not in expected:
            wrong_category += 1
            continue
        if not passes_name_filter(r.get('group'), r.get('name', '')):
            wrong_category += 1
            continue
        if r.get('group') in ('fresh_fruit', 'berries', 'raw_veg_snack') and not r.get('nutrition'):
            ref = attach_produce_reference(r)
            if ref:
                r['nutrition'] = ref
                r['isWholeProduce'] = True
        if r.get('nutrition') and r.get('detailPrice') is not None and r.get('unitPrice'):
            rows.append(r)
    print(f"Excluded {wrong_category} for wrong/missing category")
    print(f"{len(rows)} candidates have both nutrition and price")

    by_group = {}
    for r in rows:
        by_group.setdefault(r['group'], []).append(r)

    recommendations = []
    for group, items in by_group.items():
        scores = [health_score(i['nutrition']) for i in items]
        prices = [i['unitPrice'] for i in items]
        for item, hscore in zip(items, scores):
            item['_healthPct'] = percentile_rank(hscore, scores)
            item['_valuePct'] = percentile_rank(item['unitPrice'], prices, lower_is_better=True)
            item['_combined'] = 0.6 * item['_healthPct'] + 0.4 * item['_valuePct']
            # currently-discounted items get a ranking nudge so a fresh
            # weekly run naturally surfaces "good deal right now" picks
            # without needing a separate flaky deals-feed scrape
            if item.get('onSale'):
                item['_combined'] += 8
        items.sort(key=lambda i: -i['_combined'])

        seen_name_roots = set()
        picked = []
        for item in items:
            root = re.sub(r'\d+\s*(g|kg|ml|l|kpl).*$', '', item['name'].lower()).split()[0:2]
            root = tuple(root)
            if root in seen_name_roots:
                continue
            seen_name_roots.add(root)
            picked.append(item)
            if len(picked) >= 8:
                break

        for item in picked:
            n = item['nutrition']
            badges = []
            if item.get('onSale'):
                badges.append('On sale now')
            if item['_healthPct'] >= 75:
                badges.append('Healthy pick')
            if item['_valuePct'] >= 75 and len(badges) < 2:
                badges.append('Great value')
            if n['protein100'] >= 12 and len(badges) < 2:
                badges.append('High protein')
            if (n.get('sugar100') or 0) <= 3 and group != 'fresh_fruit' and len(badges) < 2:
                badges.append('Low sugar')
            if not badges:
                badges.append('Worth a look')

            recommendations.append({
                'ean': item['ean'],
                'name': item['name'],
                'brand': item.get('brand'),
                'group': group,
                'groupLabel': GROUP_LABELS[group],
                'icon': GROUP_ICON[group],
                'price': item['detailPrice'],
                'unit': item.get('detailUnit'),
                'unitPrice': item['unitPrice'],
                'unitPriceUnit': item.get('unitPriceUnit'),
                'onSale': bool(item.get('onSale')),
                'kcal100': n['kcal100'], 'protein100': n['protein100'],
                'carbs100': n.get('carbs100'), 'sugar100': n.get('sugar100'),
                'fiber100': n.get('fiber100'),
                'fat100': n.get('fat100') if n.get('fat100') is not None else n.get('fatSat100'),
                'fatSat100': n.get('fatSat100'),
                'salt100': n.get('salt100'),
                'dietTags': item.get('dietTags', []),
                'badges': badges[:2],
                'needsHeating': needs_heating(item),
                'isWholeProduce': bool(item.get('isWholeProduce')),
                'healthPct': round(item['_healthPct']),
                'valuePct': round(item['_valuePct']),
            })

    print(f"\nFinal recommendation count: {len(recommendations)}")
    from collections import Counter
    print('by group:', dict(Counter(r['group'] for r in recommendations)))

    json.dump(recommendations, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
