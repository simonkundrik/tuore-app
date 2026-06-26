# -*- coding: utf-8 -*-
"""Selects a diverse ~400-recipe batch out of the 1285 cleanly-mapped K-Ruoka
recipes: dedupe identical ingredient-signatures, cap how many recipes share
the same dominant protein so the batch isn't all-chicken, and prefer recipes
with a reasonable (3-8) ingredient count."""
import json
from collections import defaultdict

MEAT_FISH = {'chicken','cookedchicken','beef','pork','turkey','lamb','sausage','bacon',
             'chorizo','mince','salmon','tuna','whitefish','prawns','mussels','herring'}
OTHER_PROTEIN = {'tofu','chickpeas','lentils','blackbeans','eggs'}

clean = json.load(open('coverage_clean.json', encoding='utf-8'))
raw = {r['recipeId']: r for r in json.load(open('recipes_raw.json', encoding='utf-8'))}

def protein_cat(mapped):
    s = set(mapped)
    for k in ['salmon','tuna','whitefish','prawns','mussels','herring']:
        if k in s: return 'fish'
    for k in ['chicken','cookedchicken','turkey']:
        if k in s: return 'chicken'
    for k in ['beef','mince']:
        if k in s: return 'beef'
    for k in ['pork','bacon','chorizo','sausage','lamb']:
        if k in s: return 'pork_other_meat'
    for k in OTHER_PROTEIN:
        if k in s: return 'plant_protein'
    return 'vegetarian'

CAPS = {'fish': 90, 'chicken': 90, 'beef': 60, 'pork_other_meat': 60, 'plant_protein': 70, 'vegetarian': 90}

seen_sig = set()
by_cat = defaultdict(list)
for r in clean:
    n_ing = len(set(r['mapped']))
    if n_ing < 2 or n_ing > 9:
        continue
    sig = tuple(sorted(set(r['mapped'])))
    if sig in seen_sig:
        continue
    seen_sig.add(sig)
    cat = protein_cat(r['mapped'])
    full = raw.get(r['recipeId'], {})
    quality = 0
    quality += 1 if 3 <= n_ing <= 7 else 0
    quality += 1 if full.get('pictures') else 0
    by_cat[cat].append((quality, r))

selected = []
for cat, items in by_cat.items():
    items.sort(key=lambda x: -x[0])
    cap = CAPS.get(cat, 50)
    selected.extend(r for _, r in items[:cap])

print("counts by category:")
for cat, items in by_cat.items():
    cap = CAPS.get(cat, 50)
    print(f"  {cat}: {len(items)} available, taking {min(cap, len(items))}")
print(f"\ntotal selected: {len(selected)}")

out = []
for r in selected:
    full = raw[r['recipeId']]
    out.append(full)

json.dump(out, open('selected_recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
print("saved selected_recipes.json")

print("\n=== sample names ===")
for r in out[:30]:
    print(r['name']['fi'])
