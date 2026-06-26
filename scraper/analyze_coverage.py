# -*- coding: utf-8 -*-
import json
from collections import Counter
from map_ingredients import classify

DESSERT_KEYWORDS = ['kakku', 'leivos', 'piirak', 'torttu', 'jäätelö', 'kiisseli',
    'hillo', 'keksi', 'pulla', 'munkki', 'vaahto', 'mousse', 'marenki', 'pannukakku',
    'pannari', 'tiramisu', 'sorbetti', 'brita', 'parfait', 'crumble', 'cheesecake',
    'donitsi', 'muffin', 'smoothie', 'mehu', 'juoma', 'glögi', 'sangria', 'daim',
    'korvapuusti', 'pitko', 'pannacotta', 'posset', 'pavlova', 'blondie', 'brownie',
    'cookie', 'brûlée', 'brulee', 'babka', 'viineri', 'curd', 'toffee',
    'fudge', 'karamelli', 'marshmallow', 'jälkkäri', 'jälkiruok']

data = json.load(open('recipes_raw.json', encoding='utf-8'))

results = []
unknown_counter = Counter()
for r in data:
    name = (r.get('name') or {}).get('fi') or ''
    ings = r.get('ingredients') or []
    mapped_keys = []
    unknowns = []
    for ing in ings:
        sp = (ing.get('productSpelling') or {}).get('fi')
        if not sp:
            continue
        kind, val = classify(sp)
        if kind == 'mapped':
            mapped_keys.append(val)
        elif kind == 'unknown':
            unknowns.append(val)
    is_dessert = any(kw in name.lower() for kw in DESSERT_KEYWORDS)
    has_macros = r.get('energyKcalPerServing') is not None
    results.append({
        'recipeId': r.get('recipeId'), 'name': name,
        'mapped': mapped_keys, 'unknowns': unknowns,
        'is_dessert': is_dessert, 'has_macros': has_macros,
    })
    for u in unknowns:
        unknown_counter[u] += 1

clean = [r for r in results if not r['unknowns'] and len(set(r['mapped'])) >= 2
         and not r['is_dessert'] and r['has_macros']]
print(f"total recipes: {len(results)}")
print(f"clean (0 unknown, >=2 mapped, not dessert, has macros): {len(clean)}")
print()
print("=== top remaining unknown phrases (would unlock more recipes if mapped) ===")
for phrase, n in unknown_counter.most_common(60):
    print(n, phrase)

print()
print("=== sample of 20 clean recipe names ===")
for r in clean[:20]:
    print(r['name'], '->', sorted(set(r['mapped'])))

json.dump(clean, open('coverage_clean.json', 'w', encoding='utf-8'), ensure_ascii=False)
