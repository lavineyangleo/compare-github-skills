#!/usr/bin/env python3
"""Download multiple public GitHub skill repositories without executing them."""

import argparse
import json
import sys
from pathlib import Path

from skill_compare.workflow import run_comparison_download


def positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", nargs="+", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ref", action="append", default=[], metavar="INDEX=REF")
    parser.add_argument("--no-proxy", action="store_true")
    parser.add_argument("--max-download-mb", type=positive_int, default=100)
    parser.add_argument("--max-extract-mb", type=positive_int, default=400)
    args = parser.parse_args()
    if len(args.urls) < 2:
        parser.error("Provide at least two GitHub URLs.")
    refs = {}
    for item in args.ref:
        index_text, separator, ref = item.partition("=")
        if not separator or not index_text.isdigit() or not ref:
            parser.error("--ref must use INDEX=REF, such as 1=main.")
        index = int(index_text)
        if index < 1 or index > len(args.urls) or index in refs:
            parser.error("Each --ref index must identify one input URL and occur only once.")
        refs[index] = ref
    options = vars(args)
    options.pop("ref")
    manifest_path, complete = run_comparison_download(**options, refs=refs)
    print(json.dumps({"manifest": str(manifest_path), "all_projects_ready": complete}, ensure_ascii=False))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
