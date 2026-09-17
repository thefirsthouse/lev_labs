#!/usr/bin/env python3
"""Patch the previously generated lab1 GUI to make side menus compact.

Run from the project directory:
    python3 compact_ui_patch.py /path/to/lab1_vs_gui_v2

The script only edits app.py and keeps a backup app.py.bak.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "app.py"
    if not app.exists():
        print(f"Не найден {app}")
        return 2

    text = app.read_text(encoding="utf-8")
    backup = app.with_suffix(".py.bak")
    if not backup.exists():
        shutil.copy2(app, backup)

    replacements = [
        # Window / main proportions.
        ('self.geometry("1500x920")', 'self.geometry("1600x900")'),
        ('self.minsize(1200, 760)', 'self.minsize(1100, 700)'),
        ('width=300', 'width=220'),
        ('width=330', 'width=260'),
        # Make outer panels less padded.
        ('left = ttk.Frame(outer, style="Panel.TFrame", width=220)',
         'left = ttk.Frame(outer, style="Panel.TFrame", width=220)'),
        ('right = ttk.Frame(outer, style="Panel.TFrame", width=260)',
         'right = ttk.Frame(outer, style="Panel.TFrame", width=260)'),
        # Compact top bar.
        ('top.pack(fill="x", padx=10, pady=(8, 6))',
         'top.pack(fill="x", padx=8, pady=(6, 4))'),
        ('padx=(0, 6)', 'padx=(0, 3)'),
        ('padx=6)', 'padx=3)'),
        ('padx=(16, 4)', 'padx=(8, 3)'),
        # Left content spacing.
        ('pady=(14, 6)', 'pady=(8, 4)'),
        ('pady=(14, 4)', 'pady=(8, 4)'),
        ('pady=(16, 4)', 'pady=(8, 4)'),
        ('pady=(16, 5)', 'pady=(8, 4)'),
        ('pady=(14, 6)', 'pady=(8, 4)'),
        # Narrower test controls/table.
        ('width=15)', 'width=12)'),
        ('width=150)', 'width=105)'),
        ('width=60', 'width=42'),
        # Smaller text blocks on sidebars.
        ('height=17', 'height=11'),
        ('height=8', 'height=6'),
        ('height=16', 'height=9'),
    ]

    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)

    # Make panels denser without changing the timeline itself.
    text = text.replace(
        'self.snapshot.pack(fill="x", pady=(6, 12))',
        'self.snapshot.pack(fill="x", pady=(4, 7))',
    )
    text = text.replace(
        'self.detail.pack(fill="x", pady=(6, 12))',
        'self.detail.pack(fill="x", pady=(4, 7))',
    )
    text = text.replace(
        'self.stats_label.pack(anchor="w", pady=(6, 12))',
        'self.stats_label.pack(anchor="w", pady=(4, 7))',
    )
    text = text.replace(
        'self.log.pack(fill="both", expand=True, pady=(6, 0))',
        'self.log.pack(fill="both", expand=True, pady=(4, 0))',
    )

    # Reduce canvas label area slightly so timeline gets more horizontal room.
    text = text.replace('self.left_label_width = 155', 'self.left_label_width = 135')

    app.write_text(text, encoding="utf-8")
    print(f"Готово: {app}")
    print(f"Резервная копия: {backup}")
    print("Боковые панели: 220 px / 260 px; окно: 1600x900.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
