"""
modules/01-conversational/setup_db.py — Create the SQLite DB for Module 1.

Run this BEFORE starting module.py.
It creates memory_workshop.db and shows you the empty schema.

Run:  python modules/01-conversational/setup_db.py
"""

import os
import sys
import sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()

DB_PATH = "memory_workshop.db"


def setup():
    console.print()
    console.print(Rule("[bold]Module 1 — Database Setup[/bold]"))
    console.print()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS turns (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        session   TEXT NOT NULL,
        role      TEXT NOT NULL,
        content   TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()

    # Show schema
    console.print(Panel(
        f"[green]✓ Created: {DB_PATH}[/green]\n\n"
        "Table: [bold]turns[/bold]",
        border_style="green",
        title="DB Ready",
    ))
    console.print()

    tbl = Table(title="turns — schema", border_style="dim", show_lines=True)
    tbl.add_column("column", style="bold")
    tbl.add_column("type")
    tbl.add_column("description", style="dim")

    tbl.add_row("id",        "INTEGER",  "auto-increment primary key")
    tbl.add_row("session",   "TEXT",     "who is talking — e.g. 'alex-chen-session-1'")
    tbl.add_row("role",      "TEXT",     "'user' or 'assistant'")
    tbl.add_row("content",   "TEXT",     "the message text")
    tbl.add_row("timestamp", "DATETIME", "when it was saved")

    console.print(tbl)
    console.print()

    # Show current rows (empty at this point)
    rows = conn.execute("SELECT * FROM turns").fetchall()
    conn.close()

    console.print(Panel(
        f"[yellow]0 rows — table is empty[/yellow]\n\n"
        "Run module.py and uncomment STEP 1 → STEP 2 → STEP 3.\n"
        "Come back and query the DB to see rows appear:\n\n"
        f"  [bold]sqlite3 {DB_PATH}[/bold]\n"
        f"  [bold]SELECT * FROM turns;[/bold]",
        border_style="yellow",
        title="Current State",
    ))
    console.print()


if __name__ == "__main__":
    setup()
