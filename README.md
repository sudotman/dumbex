# dumbex log 

a dumb but simple regex type filtering for logs. the philosphy being that sometimes regex can be a bit strict with the extractions - this allows for more "loose" and flexible extractions where the logs exceed millions of lines. 

aka

a developer-friendly tool to extract relevant parts from large log files.

it supports two extraction modes:

1. **include-lines rules**  
   output every line that matches one of your patterns.

2. **trigger-block rules**  
   when a trigger matches, output:
   - the trigger line itself, and
   - the next **N** lines after it (e.g., 100).

![dumbex tui](https://raw.githubusercontent.com/sudotman/sudotman/refs/heads/main/demos/dumbex/Log_Extractor_2026-02-17T18_16_00_370093.svg)

## what does this repo have?
- a **reusable core engine** (`log_extractor/core.py`)
- a **CLI** (`log_extractor/cli.py`)
- a **textual TUI** (`log_extractor/tui.py`) with a clean UI


## project structure
```text
log-extractor/
  log_extractor/
    __init__.py
    rules.py
    core.py
    config.py        # optional: load/save rules JSON
    cli.py
    tui.py           # textual app
    tui.tcss         # textual styling
  README.md
```


## requirements

- CLI: **stdlib only**
- TUI:
  - `textual` 
  - `textual-fspicker` for file picker (recommended)


## installing

1) clone the repo

2) Install TUI dependencies

```bash
python -m pip install "textual>=8.0.0" textual-fspicker
```


## quick start 

suppose that you want to extract:

- all lines containing `LogTemp: [PnP]`
- plus every block starting at `LogTemp: === DebugLogSharedTagPositions` including the next 100 lines

### CLI

```bash
python -m log_extractor.cli extract \
  -i input.log \
  -o extracted.log \
  --include "LogTemp: [PnP]" \
  --block "LogTemp: === DebugLogSharedTagPositions::100"
```

### TUI

```bash
python -m log_extractor.tui
```

in the UI:

- pick input and output via **Browse…**
- add include patterns / block triggers
- click **Run extraction**

---

## how it works (conceptual)

the extractor streams the log file line-by-line and for each line, it prints the line [and saves it] if **any** of these conditions are true:

1. it matches any **include** pattern
2. it is a **trigger** line
3. it falls within “next N lines” after a trigger that fired previously

### literal vs regex mode

- Default: patterns are treated as **literal substrings**
- Optional: enable **regex** mode to treat patterns as regular expressions

## TUI usage 


```bash
python -m log_extractor.tui
```
## CLI usage

### Command

```bash
python -m log_extractor.cli extract [options]
```

### Options

- `-i, --input PATH` (required)  
  Input log file

- `-o, --output PATH` (optional)  
  Output file (default: stdout)

- `--include PATTERN` (repeatable)  
  Print any line matching PATTERN

- `--block "PATTERN::N"` (repeatable)  
  Print the trigger line + next N lines  
  If `::N` is omitted, the default `--after` value is used.

- `-n, --after N`  
  Default N lines after trigger when `::N` isn’t specified (default: 100)

- `--regex`  
  Treat patterns as regex (default: literal substring)

- `--separators`  
  Adds a separator line when a trigger fires

- `--config rules.json`  
  Load rules from a JSON config file (overrides CLI patterns)

### CLI examples

Multiple includes + multiple triggers:

```bash
python -m log_extractor.cli extract \
  -i input.log -o extracted.log \
  --include "ERROR" \
  --include "LogTemp: [PnP]" \
  --block "LogTemp: === DebugLogSharedTagPositions::120" \
  --block "SomeOtherTrigger::50"
```

Regex mode:

```bash
python -m log_extractor.cli extract \
  -i input.log -o extracted.log \
  --regex \
  --include "LogTemp: \\[PnP\\].*" \
  --block "LogTemp: === DebugLogSharedTagPositions::100"
```

---

## JSON config (optional)

if you want repeatable rule sets across a team, store them in JSON.

example `rules.json`:

```json
{
  "regex": false,
  "include": ["LogTemp: [PnP]"],
  "blocks": [
    { "trigger": "LogTemp: === DebugLogSharedTagPositions", "after": 100 }
  ]
}
```

Run:

```bash
python -m log_extractor.cli extract -i input.log -o extracted.log --config rules.json
```

---


### run button appears to do nothing?

check the **log panel** in the TUI. Common causes:
- input path doesn’t exist
- paths include quotes (handled by the TUI, but good to verify)
- no include patterns / no triggers


## misc notes

- core extraction logic lives in `core.py` so it can be reused by:
  - CLI
  - TUI
  - tests / scripts

- extraction runs in a background thread; UI stays responsive; cancel is supported.


## license
MIT.