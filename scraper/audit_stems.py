# -*- coding: utf-8 -*-
import json
from collections import Counter, defaultdict
from map_ingredients import FI_STEM_TO_KEY, classify

data = json.load(open('recipes_raw.json', encoding='utf-8'))
freq = Counter()
for r in data:
    for ing in r.get('ingredients') or []:
        sp = (ing.get('productSpelling') or {}).get('fi')
        if sp:
            freq[sp.strip().lower()] += 1

phrases = list(freq.keys())

by_stem = defaultdict(list)
for p in phrases:
    p_low = p.lower()
    for stem, key in FI_STEM_TO_KEY:
        if stem in p_low:
            by_stem[(stem, key)].append(p)
            break

for (stem, key), matched in by_stem.items():
    print(f"\n=== stem={stem!r} -> {key} ({len(matched)} distinct phrases) ===")
    for p in sorted(matched, key=lambda x: -freq[x])[:8]:
        print(f"   {freq[p]:4d}  {p}")
