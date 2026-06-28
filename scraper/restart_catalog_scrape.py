# -*- coding: utf-8 -*-
"""One-shot, safe recovery for the catalog nutrition scrape: stops any
running instance (python driver + Chrome, including anything orphaned by
a previous partial stop), verifies a clean process state, then relaunches
fresh with a new log file.

Meant to be invoked by hand (never automatically -- no cron job calls
this) whenever the admin dashboard flags the scrape as stuck or
unexpectedly not running. Read-only by default: it only prints current
process state and does nothing destructive unless run with --yes.

Runs everything inside a single Python process rather than a chain of
separate ssh commands on purpose -- a chained `pkill A; ...; pkill B`
invoked as one multi-command ssh session has, more than once, dropped the
connection between commands and left Chrome orphaned after only the
python driver was killed. One process, one ssh round trip, no gap for the
connection to drop in between steps."""
import glob
import re
import subprocess
import sys
import time
from pathlib import Path

SCRAPER_DIR = Path(__file__).parent
SCRIPT = "scrape_full_catalog_nutrition.py"
CONFIRMED = "--yes" in sys.argv


def pids_matching(pattern):
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.strip()
    return [p for p in out.splitlines() if p]


def next_log_path():
    existing = glob.glob(str(SCRAPER_DIR / "catalog_nutrition_full*.log"))
    nums = [int(m.group(1)) for f in existing for m in [re.search(r"full(\d+)\.log$", f)] if m]
    n = max(nums, default=0) + 1
    return SCRAPER_DIR / f"catalog_nutrition_full{n}.log"


def main():
    driver_pids = pids_matching(SCRIPT)
    chrome_pids = pids_matching("chrome.*chrome-profile")
    print(f"driver pids: {driver_pids or 'none'}")
    print(f"chrome pids: {chrome_pids or 'none'}")

    if not CONFIRMED:
        print("\nDry run only (no --yes passed) -- nothing was changed.")
        print("Re-run with --yes to stop the above and relaunch fresh.")
        return

    if driver_pids:
        print("\n=== stopping driver ===")
        subprocess.run(["pkill", "-f", SCRIPT])
        time.sleep(3)

    print("=== stopping any chrome (including orphaned) ===")
    subprocess.run(["pkill", "-9", "-f", "chrome.*chrome-profile"])
    time.sleep(2)

    remaining = pids_matching(SCRIPT) + pids_matching("chrome.*chrome-profile")
    if remaining:
        print(f"Still running after first attempt: {remaining} -- retrying once more")
        subprocess.run(["pkill", "-9", "-f", SCRIPT])
        subprocess.run(["pkill", "-9", "-f", "chrome.*chrome-profile"])
        time.sleep(2)
        remaining = pids_matching(SCRIPT) + pids_matching("chrome.*chrome-profile")
        if remaining:
            print(f"FAILED to reach a clean state, still running: {remaining}")
            sys.exit(1)
    print("Confirmed clean.")

    log_path = next_log_path()
    print(f"=== relaunching, logging to {log_path.name} ===")
    subprocess.Popen(
        f"cd {SCRAPER_DIR} && nohup python3 -u {SCRIPT} > {log_path.name} 2>&1 & disown",
        shell=True, cwd=str(SCRAPER_DIR),
    )
    time.sleep(3)
    new_pids = pids_matching(SCRIPT)
    if new_pids:
        print(f"Restarted successfully. New driver pid(s): {new_pids}, log: {log_path.name}")
    else:
        print("WARNING: could not confirm the new process is running -- check manually")
        sys.exit(1)


if __name__ == "__main__":
    main()
