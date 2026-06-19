"""CLI: run the scoring evaluation harness against vendor_labels.csv.

Usage:
    uv run python -m vrm_api.scoring.eval_cli
    uv run python -m vrm_api.scoring.eval_cli --json > eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import evaluate_all, format_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of the ASCII report")
    parser.add_argument("--registry", type=Path, help="Override path to vendor_registry.csv")
    parser.add_argument("--labels", type=Path, help="Override path to vendor_labels.csv")
    parser.add_argument("--save", type=Path, help="Also write JSON report to this path")
    args = parser.parse_args()

    rep = evaluate_all(registry_csv=args.registry, labels_csv=args.labels)

    if args.json:
        json.dump(rep.as_dict(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        print(format_report(rep))

    if args.save:
        args.save.write_text(json.dumps(rep.as_dict(), indent=2, default=str))
        print(f"\nSaved JSON report → {args.save}", file=sys.stderr)


if __name__ == "__main__":
    main()
