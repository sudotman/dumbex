from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.validation import Number
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    RichLog,
    Static,
)

try:
    from .core import extract_file
    from .rules import BlockRule, Rules
except ImportError:
    from core import extract_file
    from rules import BlockRule, Rules

try:
    # pip install textual-fspicker
    from textual_fspicker import FileOpen, FileSave
except Exception:
    FileOpen = None
    FileSave = None


def _clean_path(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        s = s[1:-1].strip()
    return s


class TextPrompt(ModalScreen[str | None]):
    def __init__(
        self,
        *,
        title: str,
        label: str,
        initial: str = "",
        placeholder: str = "",
    ):
        super().__init__()
        self._title = title
        self._label = label
        self._initial = initial
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="dlg_title")
        yield Label(self._label, id="dlg_label")
        yield Input(
            value=self._initial,
            placeholder=self._placeholder,
            id="dlg_input",
        )
        with Horizontal(id="dlg_buttons"):
            yield Button("Cancel", id="dlg_cancel")
            yield Button("OK", variant="primary", id="dlg_ok")

    def on_mount(self) -> None:
        self.query_one("#dlg_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dlg_cancel":
            self.dismiss(None)
            return
        value = self.query_one("#dlg_input", Input).value.strip()
        if not value:
            self.app.bell()
            return
        self.dismiss(value)


class BlockPrompt(ModalScreen[BlockRule | None]):
    def __init__(
        self,
        *,
        title: str,
        trigger: str = "",
        after: int = 100,
    ):
        super().__init__()
        self._title = title
        self._trigger = trigger
        self._after = after

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="dlg_title")
        yield Label("Trigger pattern", id="dlg_label")
        yield Input(
            value=self._trigger,
            placeholder="e.g. LogTemp: === DebugLogSharedTagPositions",
            id="blk_trigger",
        )
        yield Label("Lines after trigger (N)", id="dlg_after_label")
        yield Input(
            value=str(self._after),
            validators=[Number(minimum=0)],
            id="blk_after",
        )
        with Horizontal(id="dlg_buttons"):
            yield Button("Cancel", id="dlg_cancel")
            yield Button("OK", variant="primary", id="dlg_ok")

    def on_mount(self) -> None:
        self.query_one("#blk_trigger", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dlg_cancel":
            self.dismiss(None)
            return

        trigger = self.query_one("#blk_trigger", Input).value.strip()
        after_txt = self.query_one("#blk_after", Input).value.strip()

        if not trigger:
            self.app.bell()
            return

        try:
            after = int(after_txt)
        except ValueError:
            self.app.bell()
            return

        self.dismiss(BlockRule(trigger=trigger, after=after))


class PatternItem(ListItem):
    def __init__(self, pattern: str):
        super().__init__(Label(pattern))
        self.pattern = pattern


@dataclass
class ExtractState:
    running: bool = False


class LogExtractorTUI(App):
    CSS_PATH = "tui.tcss"
    TITLE = "dumbex"
    SUB_TITLE = "a dumb but simple log filtering"

    def __init__(self):
        super().__init__()
        self.includes: list[str] = []
        self.blocks: list[BlockRule] = []

        self._state = ExtractState(False)
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Grid(id="root"):
            with Vertical(id="files"):
                yield Static("Files", classes="section_title")

                with Horizontal(classes="row"):
                    yield Label("Input", classes="field_label")
                    yield Input(id="input_path")
                    yield Button("Browse…", id="browse_input")

                with Horizontal(classes="row"):
                    yield Label("Output", classes="field_label")
                    yield Input(id="output_path")
                    yield Button("Browse…", id="browse_output")

            with Grid(id="rules"):
                with Vertical(id="includes"):
                    yield Static("Include patterns", classes="section_title")
                    yield Static(
                        "Prints matching lines (substring by default).",
                        classes="hint",
                    )
                    yield ListView(id="include_list")
                    with Horizontal(classes="row"):
                        yield Button("Add", id="inc_add")
                        yield Button("Edit", id="inc_edit")
                        yield Button("Remove", id="inc_remove")

                with Vertical(id="blocks"):
                    yield Static("Block triggers", classes="section_title")
                    yield Static(
                        "Prints trigger line + next N lines.",
                        classes="hint",
                    )
                    table = DataTable(id="block_table")
                    table.add_columns("Trigger", "After")
                    yield table
                    with Horizontal(classes="row"):
                        yield Button("Add", id="blk_add")
                        yield Button("Edit", id="blk_edit")
                        yield Button("Remove", id="blk_remove")

            with Vertical(id="run_panel"):
                yield Static("Run", classes="section_title")
                with Horizontal(classes="row"):
                    yield Checkbox("Regex mode", id="opt_regex")
                    yield Checkbox("Separators on trigger", id="opt_sep")
                    yield Checkbox("Strip timestamps", id="opt_strip_ts")
                with Horizontal(classes="row"):
                    yield Label("Status", classes="field_label")
                    yield Static("Idle", id="status")

                yield ProgressBar(total=100, show_percentage=True, id="prog")

                with Horizontal(classes="row"):
                    yield Button(
                        "Run extraction",
                        variant="primary",
                        id="run_btn",
                    )
                    yield Button("Cancel", id="cancel_btn", disabled=True)

                yield RichLog(id="log", wrap=True)

        yield Footer()

    def on_mount(self) -> None:
        self.includes = ["LogTemp: [PnP]"]
        self.blocks = [
            BlockRule(
                trigger="LogTemp: === DebugLogSharedTagPositions",
                after=100,
            )
        ]
        self._refresh_includes()
        self._refresh_blocks()

        import textual  # local import to show version in UI

        self._log(
            f"Loaded tui.py from: {__file__}\n"
            f"Textual: {getattr(textual, '__version__', 'unknown')}\n"
            f"textual-fspicker: {'available' if FileOpen else 'missing'}"
        )

    # -------- view helpers --------
    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    def _set_status(self, msg: str) -> None:
        self.query_one("#status", Static).update(msg)

    def _set_running(self, running: bool) -> None:
        self._state.running = running
        self.query_one("#run_btn", Button).disabled = running
        self.query_one("#cancel_btn", Button).disabled = not running

    def _refresh_includes(self) -> None:
        lv = self.query_one("#include_list", ListView)
        lv.clear()
        for p in self.includes:
            lv.append(PatternItem(p))

    def _refresh_blocks(self) -> None:
        table = self.query_one("#block_table", DataTable)
        table.clear()

        for b in self.blocks:
            table.add_row(b.trigger, str(b.after))

    def _selected_include_index(self) -> int | None:
        lv = self.query_one("#include_list", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self.includes):
            return None
        return idx

    def _selected_block_index(self) -> int | None:
        table = self.query_one("#block_table", DataTable)
        coord = table.cursor_coordinate
        if coord is None:
            return None
        row = coord.row
        if row < 0 or row >= len(self.blocks):
            return None
        return row

    # -------- file picker callbacks --------
    def _set_input_path(self, picked: Any) -> None:
        if picked:
            self.query_one("#input_path", Input).value = str(picked)

    def _set_output_path(self, picked: Any) -> None:
        if picked:
            self.query_one("#output_path", Input).value = str(picked)

    # -------- extraction thread --------
    def _extract_thread(
        self,
        in_path: str,
        out_path: str,
        rules: Rules,
        separators: bool,
    ) -> None:
        last_lines = 0

        def on_progress(lines: int, done: bool) -> None:
            nonlocal last_lines
            last_lines = lines
            if done:
                return

            def ui() -> None:
                self._set_status(f"Running… {lines:,} lines")
                bar = self.query_one("#prog", ProgressBar)
                if bar.progress >= bar.total:
                    bar.update(progress=0)
                else:
                    bar.advance(1)

            self.call_from_thread(ui)

        try:
            extract_file(
                in_path,
                out_path,
                rules,
                include_separators=separators,
                progress_cb=on_progress,
                cancel_event=self._cancel_event,
            )
            cancelled = self._cancel_event.is_set()

            def ui_done() -> None:
                msg = "Cancelled" if cancelled else "Completed"
                self._set_status(f"{msg}. {last_lines:,} lines")
                self._log(f"{msg}. Output: {out_path}")
                self.query_one("#prog", ProgressBar).update(progress=100)
                self._set_running(False)

            self.call_from_thread(ui_done)
        except Exception as e:

            def ui_err() -> None:
                self._set_status("Error")
                self._log(f"Error: {e}")
                self._set_running(False)

            self.call_from_thread(ui_err)

    # -------- event handling (stable across versions) --------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "browse_input":
            if FileOpen is None:
                self._log(
                    "File picker missing. Install: pip install textual-fspicker"
                )
                return
            self.push_screen(
                FileOpen(Path.cwd()),
                callback=self._set_input_path,
            )
            return

        if bid == "browse_output":
            if FileSave is None:
                self._log(
                    "File picker missing. Install: pip install textual-fspicker"
                )
                return
            self.push_screen(
                FileSave(Path.cwd()),
                callback=self._set_output_path,
            )
            return

        if bid == "inc_add":
            self.push_screen(
                TextPrompt(
                    title="Add include pattern",
                    label="Pattern:",
                    placeholder="e.g. LogTemp: [PnP] Tag",
                ),
                callback=self._inc_add_done,
            )
            return

        if bid == "inc_edit":
            idx = self._selected_include_index()
            if idx is None:
                self._log("Select an include pattern first.")
                return

            def done(value: str | None) -> None:
                if not value:
                    return
                self.includes[idx] = value
                self._refresh_includes()

            self.push_screen(
                TextPrompt(
                    title="Edit include pattern",
                    label="Pattern:",
                    initial=self.includes[idx],
                ),
                callback=done,
            )
            return

        if bid == "inc_remove":
            idx = self._selected_include_index()
            if idx is None:
                return
            self.includes.pop(idx)
            self._refresh_includes()
            return

        if bid == "blk_add":
            self.push_screen(
                BlockPrompt(title="Add block trigger", after=100),
                callback=self._blk_add_done,
            )
            return

        if bid == "blk_edit":
            idx = self._selected_block_index()
            if idx is None:
                self._log("Select a block row first.")
                return

            b = self.blocks[idx]

            def done(value: BlockRule | None) -> None:
                if not value:
                    return
                self.blocks[idx] = value
                self._refresh_blocks()

            self.push_screen(
                BlockPrompt(
                    title="Edit block trigger",
                    trigger=b.trigger,
                    after=b.after,
                ),
                callback=done,
            )
            return

        if bid == "blk_remove":
            idx = self._selected_block_index()
            if idx is None:
                return
            self.blocks.pop(idx)
            self._refresh_blocks()
            return

        if bid == "run_btn":
            if self._state.running:
                return

            in_path = _clean_path(self.query_one("#input_path", Input).value)
            out_path = _clean_path(self.query_one("#output_path", Input).value)
            self.query_one("#input_path", Input).value = in_path
            self.query_one("#output_path", Input).value = out_path

            if not in_path or not out_path:
                self._log("Input and Output paths are required.")
                return
            if not Path(in_path).exists():
                self._log(f"Input not found: {in_path}")
                return
            if not self.includes and not self.blocks:
                self._log("Add at least one include pattern or block trigger.")
                return

            rules = Rules(
                include=list(self.includes),
                blocks=list(self.blocks),
                regex=self.query_one("#opt_regex", Checkbox).value,
                strip_timestamps=self.query_one("#opt_strip_ts", Checkbox).value,
            )
            separators = self.query_one("#opt_sep", Checkbox).value

            self._cancel_event.clear()
            self._set_running(True)
            self._set_status("Running…")
            self.query_one("#prog", ProgressBar).update(total=100, progress=0)
            self._log("Started extraction…")

            self._thread = threading.Thread(
                target=self._extract_thread,
                args=(in_path, out_path, rules, separators),
                daemon=True,
            )
            self._thread.start()
            return

        if bid == "cancel_btn":
            if not self._state.running:
                return
            self._cancel_event.set()
            self._set_status("Cancelling…")
            self._log("Cancel requested.")
            return

    def _inc_add_done(self, value: str | None) -> None:
        if not value:
            return
        self.includes.append(value)
        self._refresh_includes()

    def _blk_add_done(self, value: BlockRule | None) -> None:
        if not value:
            return
        self.blocks.append(value)
        self._refresh_blocks()


def main() -> None:
    LogExtractorTUI().run()


if __name__ == "__main__":
    main()