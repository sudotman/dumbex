from __future__ import annotations

import argparse

from .config import load_rules_json
from .core import extract_file
from .rules import BlockRule, Rules


def _parse_block(s: str, default_after: int) -> BlockRule:
    if "::" in s:
        trigger, n = s.rsplit("::", 1)
        return BlockRule(trigger=trigger.strip(), after=int(n.strip()))
    return BlockRule(trigger=s.strip(), after=default_after)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generic log extractor")
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--include", action="append", default=[])
    p.add_argument("--block", action="append", default=[])
    p.add_argument("-n", "--after", type=int, default=100)
    p.add_argument("--regex", action="store_true")
    p.add_argument("--separators", action="store_true")
    p.add_argument("--config", default=None)

    args = p.parse_args(argv)

    if args.config:
        rules = load_rules_json(args.config)
    else:
        blocks = [_parse_block(b, args.after) for b in args.block]
        rules = Rules(include=args.include, blocks=blocks, regex=args.regex)

    extract_file(
        args.input,
        args.output,
        rules,
        include_separators=args.separators,
    )