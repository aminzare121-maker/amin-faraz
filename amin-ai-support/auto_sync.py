#!/usr/bin/env python3
"""Keep each configured GitHub project up to date while this process is running.
Does not install a system service, daemonize, or silently deploy code.
"""
import argparse
from datetime import datetime, timezone
import json
import time
from amin_support import SupportEngine, sync_one


def run_cycle(engine):
    outcomes = []
    for project in engine.projects.values():
        if not project.get("git_url") or not project.get("ref"):
            outcomes.append({"project": project["id"], "skipped": "no verified GitHub source"})
            continue
        try:
            outcomes.append(sync_one(project, engine.knowledge))
        except Exception as exc:
            outcomes.append({"project": project["id"], "error": str(exc)})
    return outcomes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=int, default=21600)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval_seconds < 300:
        parser.error("Interval must be at least 300 seconds")
    engine = SupportEngine()
    while True:
        print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
                          "results": run_cycle(engine)}, ensure_ascii=False), flush=True)
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
