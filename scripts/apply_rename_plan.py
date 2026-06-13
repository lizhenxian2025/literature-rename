from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


def within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="CSV created by build_rename_plan.py.")
    parser.add_argument("--execute", action="store_true", help="Actually rename files. Default is dry-run.")
    parser.add_argument("--allow-review", action="store_true", help="Also apply rows marked needs_review=true.")
    args = parser.parse_args()

    plan = Path(args.plan).resolve()
    rows = list(csv.DictReader(plan.open(encoding="utf-8-sig")))
    root = plan.parent.parent if plan.parent.name == "rename_work" else plan.parent
    log_path = plan.parent / f"rename_action_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fields = ["index", "status", "original_path", "final_path", "message"]
    planned = same = skipped_review = errors = 0

    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            source = Path(row["original_path"])
            target = Path(row["final_path"])
            message = ""
            review = row.get("needs_review", "").lower() == "true"
            if review and not args.allow_review:
                status = "skipped_review"
                skipped_review += 1
            elif not within_root(source, root) or not within_root(target, root):
                status = "error"
                message = "path outside root"
                errors += 1
            elif source.name == target.name:
                status = "skipped_same_name"
                same += 1
            elif source.parent.resolve() == target.parent.resolve() and source.name.lower() == target.name.lower():
                planned += 1
                if args.execute:
                    temp = source.with_name(f".__codex_case_rename_{row['index']}{source.suffix}")
                    if temp.exists():
                        status = "error"
                        message = "temporary path exists"
                        errors += 1
                        planned -= 1
                    else:
                        source.rename(temp)
                        temp.rename(target)
                        status = "renamed_case_only"
                else:
                    status = "dry_run_case_only"
            elif not source.exists():
                status = "error"
                message = "source does not exist"
                errors += 1
            elif target.exists():
                status = "error"
                message = "target already exists"
                errors += 1
            else:
                planned += 1
                if args.execute:
                    source.rename(target)
                    status = "renamed"
                else:
                    status = "dry_run"
            writer.writerow(
                {
                    "index": row.get("index", ""),
                    "status": status,
                    "original_path": str(source),
                    "final_path": str(target),
                    "message": message,
                }
            )

    print(f"mode={'execute' if args.execute else 'dry-run'}")
    print(f"planned={planned}")
    print(f"same={same}")
    print(f"skipped_review={skipped_review}")
    print(f"errors={errors}")
    print(f"log={log_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
