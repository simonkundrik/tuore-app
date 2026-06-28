# -*- coding: utf-8 -*-
"""One-time migration: regenerates the `steps` text for every existing
recipe in index.html using the improved gen_steps()/air_fryer_steps()
templates (prep hints like "diced onion"/"minced garlic", consistent heat
levels, doneness cues specific to what's actually being cooked) -- brings
already-shipped recipes in line with the same clarity improvements new
recipes get automatically going forward.

Only the `steps` field changes. id/name/macros/ing/equip/photo/everything
else in each recipe is left completely untouched. Archetype is re-derived
from the recipe's own real `ing` array via classify() (deterministic --
same ingredients always classify the same way, so this never changes
which dish type a recipe is), except for air-fryer recipes (equip
contains 'airfryer'), which always used a separate, equipment-specific
template and still do.

Air-fryer temp is re-derived from the lead protein's default (the same
table the original generation used) rather than recovered from each
recipe's original source text, since that real-temp extraction depended
on the raw scrape data and a sourceUrl that was never persisted into
index.html itself. Minor precision loss (most defaults are 180-200°C
either way) traded for not needing to re-cross-reference raw scrape
files by name. Cook time uses the recipe's own stored `time` field."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from generate_from_foodcom import classify, gen_steps
from build_airfryer_recipes import air_fryer_steps, PROTEIN_TEMP_DEFAULT

HTML_PATH = Path(__file__).parent.parent / "index.html"


def steparr(steps):
    return '[' + ','.join(json.dumps(s, ensure_ascii=False) for s in steps) + ']'


def main():
    html = HTML_PATH.read_text(encoding="utf-8")
    start = html.index("\nlet meals=[") + len("\nlet meals=[")
    end = html.index("\n];\n", start)
    body = html[start:end]
    chunks = body.split("{id:'")

    changed = 0
    skipped = 0
    new_chunks = [chunks[0]]
    for chunk in chunks[1:]:
        if 'steps:[' not in chunk or 'ing:[' not in chunk:
            new_chunks.append(chunk)
            skipped += 1
            continue

        equip_m = re.search(r"equip:\[(.*?)\]", chunk)
        equip = re.findall(r"'(\w+)'", equip_m.group(1)) if equip_m else []
        ing_m = re.search(r"ing:\[(.*?)\]", chunk)
        refs = re.findall(r"ref:'(\w+)'", ing_m.group(1)) if ing_m else []
        time_m = re.search(r"time:(\d+)", chunk)
        time = int(time_m.group(1)) if time_m else 25

        if not refs:
            new_chunks.append(chunk)
            skipped += 1
            continue

        if 'airfryer' in equip:
            lead_protein = next((r for r in refs if r in PROTEIN_TEMP_DEFAULT), None)
            temp_c = PROTEIN_TEMP_DEFAULT.get(lead_protein, 200)
            # stored `time` is prep+cook combined; the original real cookTime
            # (not persisted anywhere we can recover) is never the full
            # total, and this codebase already assumes ~5min prep as its own
            # fallback elsewhere when a real prepTime is missing -- without
            # this, e.g. a 20min total recipe reads "air-fry for 17-20 min"
            # instead of the ~7-10 min it actually needs
            cook_min = max(time - 5, 6)
            new_steps = air_fryer_steps(refs, temp_c, cook_min)
        else:
            archetype = classify(refs)
            new_steps, _ = gen_steps(archetype, refs, time)

        old_steps_block = chunk[chunk.index('steps:['):chunk.index('],ing:') + 1]
        new_steps_block = 'steps:' + steparr(new_steps)
        new_chunk = chunk.replace(old_steps_block, new_steps_block, 1)
        new_chunks.append(new_chunk)
        changed += 1

    new_body = "{id:'".join(new_chunks)
    html2 = html[:start] + new_body + html[end:]
    HTML_PATH.write_text(html2, encoding="utf-8")
    print(f"Regenerated steps for {changed} recipes ({skipped} skipped -- no steps/ing field found)")


if __name__ == "__main__":
    main()
