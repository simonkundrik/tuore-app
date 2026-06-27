# -*- coding: utf-8 -*-
"""Picks the lightest real option within each sauce category (mayo vs
mayo, ketchup vs ketchup, etc.) rather than across categories, since
"healthy ketchup" and "healthy mayo" mean very different absolute
numbers -- a mustard will always look "healthier" than a mayo by raw
calories, but that's not a useful comparison. Ranked purely on health
(no value blending like Grab & Go) since the ask here is specifically
the healthiest real option, not the best deal."""
import json
import re
from pathlib import Path
from statistics import median

IN_PATH = Path(__file__).parent / "sauces_details_raw.json"
OUT_PATH = Path(__file__).parent / "sauces_recommendations.json"

# free-text search returns "best match" results that are sometimes only
# loosely related (e.g. a "sinappi" search surfacing a mustard-glazed
# ham) -- requiring the product's own name to contain the category's
# real word is the main defense against recommending something that
# isn't actually that sauce
GROUP_NAME_FILTER = {
    'mayo': ['majoneesi'],
    'ketchup': ['ketsuppi'],
    'mustard': ['sinappi'],
    'bbq': ['grillikastike', 'bbq-kastike', 'bbq kastike'],
    'hot_sauce': ['chilikastike', 'chili kastike', 'sriracha'],
    'soy_sauce': ['soijakastike', 'soija kastike'],
    'aioli': ['aioli'],
    'dressing': ['salaattikastike', 'salaatinkastike'],
    'remoulade': ['remoulade', 'remulaad'],
}

GROUP_LABELS = {
    'mayo': 'Mayo', 'ketchup': 'Ketchup', 'mustard': 'Mustard', 'bbq': 'BBQ sauce',
    'hot_sauce': 'Hot sauce', 'soy_sauce': 'Soy sauce', 'aioli': 'Aioli',
    'dressing': 'Salad dressing', 'remoulade': 'Remoulade',
}
GROUP_ICON = {
    'mayo': 'ti-bowl', 'ketchup': 'ti-bowl', 'mustard': 'ti-bowl', 'bbq': 'ti-bowl',
    'hot_sauce': 'ti-flame', 'soy_sauce': 'ti-bowl', 'aioli': 'ti-bowl',
    'dressing': 'ti-bowl', 'remoulade': 'ti-bowl',
}


def passes_name_filter(group, name):
    words = GROUP_NAME_FILTER.get(group)
    if not words:
        return True
    return any(w in name.lower() for w in words)


def health_score(n):
    # lower calories/sugar/saturated fat/salt is better; no protein
    # reward since sauces aren't a protein source
    return (-0.05 * (n.get('kcal100') or 0)
            - 2 * (n.get('sugar100') or 0)
            - 2 * (n.get('fatSat100') or 0)
            - 3 * (n.get('salt100') or 0))


def percentile_rank(value, all_values, lower_is_better=True):
    if not all_values:
        return 50
    sorted_vals = sorted(all_values, reverse=lower_is_better)
    better_count = sum(1 for v in sorted_vals if (v <= value if lower_is_better else v >= value))
    return round(100 * (1 - better_count / len(sorted_vals)) + 100 / len(sorted_vals))


def main():
    data = json.load(open(IN_PATH, encoding="utf-8"))
    rows = []
    excluded = 0
    for r in data:
        if not passes_name_filter(r.get('group'), r.get('name', '')):
            excluded += 1
            continue
        if r.get('nutrition') and r.get('detailPrice') is not None:
            rows.append(r)
    print(f"Excluded {excluded} for not matching their category's name filter")
    print(f"{len(rows)} candidates have both nutrition and price")

    by_group = {}
    for r in rows:
        by_group.setdefault(r['group'], []).append(r)

    recommendations = []
    for group, items in by_group.items():
        scores = [health_score(i['nutrition']) for i in items]
        for item, hscore in zip(items, scores):
            item['_healthPct'] = percentile_rank(-hscore, [-s for s in scores], lower_is_better=True)
        items.sort(key=lambda i: -i['_healthPct'])

        seen_name_roots = set()
        picked = []
        for item in items:
            root = re.sub(r'\d+\s*(g|kg|ml|l|kpl).*$', '', item['name'].lower()).split()[0:2]
            root = tuple(root)
            if root in seen_name_roots:
                continue
            seen_name_roots.add(root)
            picked.append(item)
            if len(picked) >= 5:
                break

        for item in picked:
            n = item['nutrition']
            badges = []
            if item['_healthPct'] >= 90:
                badges.append('Healthiest pick')
            if (n.get('sugar100') or 0) <= 2:
                badges.append('Low sugar')
            elif (n.get('salt100') or 0) <= 1:
                badges.append('Low salt')
            elif (n.get('fatSat100') or 0) <= 2:
                badges.append('Low sat. fat')
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
                'unitPrice': item.get('unitPrice'),
                'unitPriceUnit': item.get('unitPriceUnit'),
                'onSale': bool(item.get('onSale')),
                'kcal100': n['kcal100'],
                'fat100': n.get('fat100'),
                'fatSat100': n.get('fatSat100'),
                'carbs100': n.get('carbs100'),
                'sugar100': n.get('sugar100'),
                'salt100': n.get('salt100'),
                'dietTags': item.get('dietTags', []),
                'badges': badges[:2],
                'healthPct': round(item['_healthPct']),
            })

    print(f"\nFinal recommendation count: {len(recommendations)}")
    from collections import Counter
    print('by group:', dict(Counter(r['group'] for r in recommendations)))

    json.dump(recommendations, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
