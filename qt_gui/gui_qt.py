from __future__ import annotations

import threading
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from .core import extract_file
    from .rules import BlockRule, Rules
except ImportError:
    from core import extract_file
    from rules import BlockRule, Rules


class TextPrompt(QDialog):
    def __init__(self, title: str, label: str, initial: str = ""):
        super().__init__()
        self.setWindowTitle(title)
        self.value = initial

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))

        self.edit = QLineEdit()
        self.edit.setText(initial)
        layout.addWidget(self.edit)

        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def get(self) -> str:
        return self.edit.text().strip()


class ExtractWorker(QThread):
    progress = Signal(int)
    done = Signal(int, bool, str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        rules: Rules,
        separators: bool,
        cancel_event: threading.Event,
    ):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.rules = rules
        self.separators = separators
        self.cancel_event = cancel_event

    def run(self):
        last = 0

        def cb(lines: int, finished: bool):
            nonlocal last
            last = lines
            if not finished:
                self.progress.emit(lines)

        try:
            extract_file(
                self.input_path,
                self.output_path,
                self.rules,
                include_separators=self.separators,
                progress_cb=cb,
                cancel_event=self.cancel_event,
            )
            cancelled = self.cancel_event.is_set()
            msg = "Cancelled" if cancelled else "Completed"
            self.done.emit(last, cancelled, msg)
        except Exception as e:
            self.done.emit(last, False, f"Error: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Extractor")
        self.setMinimumWidth(900)

        self.cancel_event = threading.Event()
        self.worker: ExtractWorker | None = None

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setSpacing(12)

        # Files
        files = QGroupBox("Files")
        files_layout = QFormLayout(files)

        self.input_edit = QLineEdit()
        self.output_edit = QLineEdit()

        in_row = QHBoxLayout()
        in_row.addWidget(self.input_edit, 1)
        in_btn = QPushButton("Browse…")
        in_btn.clicked.connect(self.pick_input)
        in_row.addWidget(in_btn)

        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit, 1)
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self.pick_output)
        out_row.addWidget(out_btn)

        files_layout.addRow("Input log", in_row)
        files_layout.addRow("Output file", out_row)

        # Rules
        rules_box = QGroupBox("Rules")
        rules_layout = QHBoxLayout(rules_box)
        rules_layout.setSpacing(16)

        # Include patterns
        inc_col = QVBoxLayout()
        inc_head = QHBoxLayout()
        inc_head.addWidget(QLabel("Include patterns"))
        inc_head.addStretch(1)
        add_inc = QPushButton("Add")
        edit_inc = QPushButton("Edit")
        rem_inc = QPushButton("Remove")
        add_inc.clicked.connect(self.add_include)
        edit_inc.clicked.connect(self.edit_include)
        rem_inc.clicked.connect(self.remove_include)
        inc_head.addWidget(add_inc)
        inc_head.addWidget(edit_inc)
        inc_head.addWidget(rem_inc)

        self.include_list = QListWidget()
        self.include_list.setMinimumWidth(360)
        inc_hint = QLabel(
            "Matches print single lines (e.g. LogTemp: [PnP])."
        )
        inc_hint.setStyleSheet("color: #666;")

        inc_col.addLayout(inc_head)
        inc_col.addWidget(self.include_list, 1)
        inc_col.addWidget(inc_hint)

        # Block rules
        blk_col = QVBoxLayout()
        blk_head = QHBoxLayout()
        blk_head.addWidget(QLabel("Block triggers"))
        blk_head.addStretch(1)
        add_blk = QPushButton("Add")
        edit_blk = QPushButton("Edit")
        rem_blk = QPushButton("Remove")
        add_blk.clicked.connect(self.add_block)
        edit_blk.clicked.connect(self.edit_block)
        rem_blk.clicked.connect(self.remove_block)
        blk_head.addWidget(add_blk)
        blk_head.addWidget(edit_blk)
        blk_head.addWidget(rem_blk)

        self.block_table = QTableWidget(0, 2)
        self.block_table.setHorizontalHeaderLabels(["Trigger", "After"])
        self.block_table.horizontalHeader().setStretchLastSection(True)
        self.block_table.setMinimumWidth(420)

        blk_hint = QLabel(
            "Triggers print the trigger line + N following lines."
        )
        blk_hint.setStyleSheet("color: #666;")

        blk_col.addLayout(blk_head)
        blk_col.addWidget(self.block_table, 1)
        blk_col.addWidget(blk_hint)

        rules_layout.addLayout(inc_col, 1)
        rules_layout.addLayout(blk_col, 1)

        # Run options
        run_box = QGroupBox("Run")
        run_layout = QHBoxLayout(run_box)

        self.regex_cb = QCheckBox("Regex mode")
        self.sep_cb = QCheckBox("Add separators on trigger")

        self.default_after = QSpinBox()
        self.default_after.setRange(0, 50000)
        self.default_after.setValue(100)

        run_layout.addWidget(self.regex_cb)
        run_layout.addWidget(self.sep_cb)
        run_layout.addSpacing(16)
        run_layout.addWidget(QLabel("Default N after"))
        run_layout.addWidget(self.default_after)
        run_layout.addStretch(1)

        self.status = QLabel("Idle")
        self.status.setStyleSheet("color: #333;")

        self.run_btn = QPushButton("Run extraction")
        self.run_btn.clicked.connect(self.start)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel)

        run_layout.addWidget(self.status)
        run_layout.addWidget(self.cancel_btn)
        run_layout.addWidget(self.run_btn)

        outer.addWidget(files)
        outer.addWidget(rules_box, 1)
        outer.addWidget(run_box)

        # Sensible defaults (you can remove these)
        self.include_list.addItem("LogTemp: [PnP]")
        self.add_block_row(
            "LogTemp: === DebugLogSharedTagPositions", 100
        )

    def pick_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select input log"
        )
        if path:
            self.input_edit.setText(path)

    def pick_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select output file"
        )
        if path:
            self.output_edit.setText(path)

    # --- include list actions ---
    def add_include(self):
        dlg = TextPrompt(
            "Add include pattern",
            "Include pattern (literal substring or regex):",
        )
        if dlg.exec():
            val = dlg.get()
            if val:
                self.include_list.addItem(val)

    def edit_include(self):
        item = self.include_list.currentItem()
        if not item:
            return
        dlg = TextPrompt(
            "Edit include pattern",
            "Include pattern:",
            item.text(),
        )
        if dlg.exec():
            val = dlg.get()
            if val:
                item.setText(val)

    def remove_include(self):
        row = self.include_list.currentRow()
        if row >= 0:
            self.include_list.takeItem(row)

    # --- block table actions ---
    def add_block_row(self, trigger: str, after: int):
        r = self.block_table.rowCount()
        self.block_table.insertRow(r)
        self.block_table.setItem(r, 0, QTableWidgetItem(trigger))
        self.block_table.setItem(r, 1, QTableWidgetItem(str(after)))

    def add_block(self):
        dlg = TextPrompt(
            "Add block trigger",
            "Trigger pattern (optionally append ::N in CLI; here set N "
            "separately):",
        )
        if not dlg.exec():
            return
        trigger = dlg.get()
        if not trigger:
            return
        self.add_block_row(trigger, int(self.default_after.value()))

    def edit_block(self):
        r = self.block_table.currentRow()
        if r < 0:
            return
        trigger_item = self.block_table.item(r, 0)
        after_item = self.block_table.item(r, 1)
        trigger = (trigger_item.text() if trigger_item else "").strip()
        after_txt = (after_item.text() if after_item else "").strip()

        dlg = TextPrompt("Edit trigger", "Trigger pattern:", trigger)
        if not dlg.exec():
            return
        new_trigger = dlg.get()
        if not new_trigger:
            return

        after_dlg = TextPrompt(
            "Edit N", "Lines after trigger (integer):", after_txt
        )
        if not after_dlg.exec():
            return
        try:
            new_after = int(after_dlg.get())
        except ValueError:
            QMessageBox.warning(self, "Invalid N", "N must be an integer.")
            return

        self.block_table.setItem(r, 0, QTableWidgetItem(new_trigger))
        self.block_table.setItem(r, 1, QTableWidgetItem(str(new_after)))

    def remove_block(self):
        r = self.block_table.currentRow()
        if r >= 0:
            self.block_table.removeRow(r)

    def build_rules(self) -> Rules:
        include = [
            self.include_list.item(i).text()
            for i in range(self.include_list.count())
        ]

        blocks: list[BlockRule] = []
        for r in range(self.block_table.rowCount()):
            trig_item = self.block_table.item(r, 0)
            after_item = self.block_table.item(r, 1)
            trigger = (trig_item.text() if trig_item else "").strip()
            after_txt = (after_item.text() if after_item else "").strip()
            if not trigger:
                continue
            try:
                after = int(after_txt)
            except ValueError:
                after = int(self.default_after.value())
            blocks.append(BlockRule(trigger=trigger, after=after))

        return Rules(include=include, blocks=blocks, regex=self.regex_cb.isChecked())

    def start(self):
        in_path = self.input_edit.text().strip()
        out_path = self.output_edit.text().strip()

        if not in_path:
            QMessageBox.warning(self, "Missing input", "Pick an input log.")
            return
        if not out_path:
            QMessageBox.warning(self, "Missing output", "Pick an output file.")
            return

        rules = self.build_rules()
        if not rules.include and not rules.blocks:
            QMessageBox.warning(
                self, "No rules", "Add at least one include or block rule."
            )
            return

        self.cancel_event.clear()
        self.set_running(True)
        self.status.setText("Running…")

        self.worker = ExtractWorker(
            in_path,
            out_path,
            rules,
            self.sep_cb.isChecked(),
            self.cancel_event,
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def cancel(self):
        self.cancel_event.set()
        self.status.setText("Cancelling…")

    def set_running(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def on_progress(self, lines: int):
        self.status.setText(f"Running… processed {lines:,} lines")

    def on_done(self, lines: int, cancelled: bool, msg: str):
        self.set_running(False)
        if msg.startswith("Error:"):
            self.status.setText("Error")
            QMessageBox.critical(self, "Extraction failed", msg)
            return
        suffix = " (cancelled)" if cancelled else ""
        self.status.setText(f"{msg}. Processed {lines:,} lines{suffix}.")


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()