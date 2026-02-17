from __future__ import annotations

import json

from .rules import BlockRule, Rules


def load_rules_json(path: str) -> Rules:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    include = list(data.get("include", []) or [])
    regex = bool(data.get("regex", False))
    blocks_in = list(data.get("blocks", []) or [])
    blocks = [
        BlockRule(
            trigger=b["trigger"],
            after=int(b.get("after", 100)),
        )
        for b in blocks_in
    ]
    return Rules(include=include, blocks=blocks, regex=regex)


def save_rules_json(path: str, rules: Rules):
    data = {
        "regex": rules.regex,
        "include": rules.include,
        "blocks": [
            {"trigger": b.trigger, "after": b.after} for b in rules.blocks
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")