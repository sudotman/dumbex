from __future__ import annotations

import re
import threading
from typing import Callable, TextIO

try:
    from .rules import Rules
except ImportError:
    from rules import Rules


ProgressCb = Callable[[int, bool], None]


def _compile_patterns(patterns: list[str], regex: bool):
    if not regex:
        return patterns, None
    return None, [re.compile(p) for p in patterns]


def _matches(line: str, literals, regexes) -> bool:
    if literals is not None:
        return any(p in line for p in literals)
    return any(r.search(line) is not None for r in (regexes or []))


def extract_file(
    input_path: str,
    output_path: str | None,
    rules: Rules,
    *,
    include_separators: bool = False,
    progress_cb: ProgressCb | None = None,
    cancel_event: threading.Event | None = None,
):
    include_literals, include_regexes = _compile_patterns(
        rules.include, rules.regex
    )

    triggers = [b.trigger for b in rules.blocks]
    trig_literals, trig_regexes = _compile_patterns(triggers, rules.regex)
    after_by_idx = [b.after for b in rules.blocks]

    active = [0] * len(rules.blocks)

    fin = open(input_path, "r", encoding="utf-8", errors="replace")
    fout = (
        open(output_path, "w", encoding="utf-8", errors="replace")
        if output_path
        else None
    )

    def emit(s: str):
        if fout:
            fout.write(s)
        else:
            print(s, end="")

    try:
        line_no = 0
        for line in fin:
            line_no += 1

            if cancel_event is not None and cancel_event.is_set():
                break

            print_this = False

            # A) Include rules
            if rules.include and _matches(
                line, include_literals, include_regexes
            ):
                print_this = True

            # B) Block rules
            if rules.blocks:
                hit_idxs: list[int]
                if trig_literals is not None:
                    hit_idxs = [
                        i
                        for i, t in enumerate(trig_literals)
                        if t in line
                    ]
                else:
                    hit_idxs = [
                        i
                        for i, r in enumerate(trig_regexes or [])
                        if r.search(line)
                    ]

                if hit_idxs:
                    print_this = True
                    for i in hit_idxs:
                        active[i] = max(active[i], after_by_idx[i])

                    if include_separators:
                        emit(
                            "\n"
                            f"----- BLOCK TRIGGER @ line {line_no} "
                            f"(matched {len(hit_idxs)} rule(s)) -----\n"
                        )
                elif any(x > 0 for x in active):
                    print_this = True
                    active = [max(0, x - 1) for x in active]

            if print_this:
                emit(line)

            if progress_cb and (line_no % 5000 == 0):
                progress_cb(line_no, False)

        if progress_cb:
            progress_cb(line_no, True)
    finally:
        fin.close()
        if fout:
            fout.close()