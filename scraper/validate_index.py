# -*- coding: utf-8 -*-
"""Shared sanity checks run before any scheduled job commits index.html.
Catches a scrape gone badly wrong (truncated file, P dict wiped out,
meals/GRABGO collapsed to near-zero) before it ever reaches git, let alone
an unattended auto-push to the live site."""
import re
from pathlib import Path

HTML_PATH = Path(__file__).parent.parent / "index.html"


def validate(html=None):
    if html is None:
        html = HTML_PATH.read_text(encoding="utf-8")
    errors = []

    for open_c, close_c, name in [('{', '}', 'braces'), ('[', ']', 'brackets'), ('(', ')', 'parens')]:
        o, c = html.count(open_c), html.count(close_c)
        if o != c:
            errors.append(f"{name} unbalanced: {o} open vs {c} close")

    p_dict_count = len(re.findall(r'\n\w+:\{"nm":', html))
    if p_dict_count != 109:
        errors.append(f"P dict has {p_dict_count} entries, expected 109")

    meals_count = len(re.findall(r"\{id:'", html))
    if meals_count < 600:
        errors.append(f"meals array suspiciously small: {meals_count} entries (expected 1000+)")

    if "var GRABGO=[" not in html:
        errors.append("GRABGO array missing entirely")
    else:
        grabgo_count = len(re.findall(r"\{ean:'", html))
        if grabgo_count < 20:
            errors.append(f"GRABGO array suspiciously small: {grabgo_count} entries (expected 50+)")

    # SAUCES is new and may legitimately not exist yet (e.g. its first
    # scheduled scrape hasn't found anything to insert) -- only check
    # it's not suspiciously small once it actually exists
    sauces_block = re.search(r"\nvar SAUCES=\[(.*?)\n\];\n", html, re.DOTALL)
    if sauces_block:
        sauces_count = len(re.findall(r"\{ean:'", sauces_block.group(1)))
        if sauces_count < 5:
            errors.append(f"SAUCES array suspiciously small: {sauces_count} entries (expected 10+)")

    return (len(errors) == 0, errors)


if __name__ == "__main__":
    ok, errors = validate()
    if ok:
        print("OK: index.html passes all sanity checks")
    else:
        print("FAILED:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)
