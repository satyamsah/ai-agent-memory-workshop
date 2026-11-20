"""
modules/02-extraction/setup_db.py — Create the SQLite DB for Module 2.

Run this BEFORE starting module.py.
It creates the memories and cache tables and shows the empty schema.

Run:  python modules/02-extraction/setup_db.py
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
    console.print(Rule("[bold]Module 2 — Database Setup[/bold]"))
    console.print()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   TEXT NOT NULL,
        type      TEXT NOT NULL,
        content   TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cache (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   TEXT NOT NULL,
        question  TEXT NOT NULL,
        answer    TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()

    console.print(Panel(
        f"[green]✓ {DB_PATH}[/green]\n\n"
        "New tables: [bold]memories[/bold], [bold]cache[/bold]",
        border_style="green",
        title="DB Ready",
    ))
    console.print()

    # Show live SELECT output for memories
    mem_rows = conn.execute("SELECT * FROM memories").fetchall()
    mem_tbl = Table(title="SELECT * FROM memories", border_style="yellow", show_lines=True)
    mem_tbl.add_column("id", style="dim")
    mem_tbl.add_column("user_id")
    mem_tbl.add_column("type")
    mem_tbl.add_column("content")
    mem_tbl.add_column("timestamp", style="dim")
    if mem_rows:
        for row in mem_rows:
            mem_tbl.add_row(*[str(c) for c in row])
    else:
        mem_tbl.add_row("[dim]—[/dim]", "[dim]—[/dim]", "[dim]—[/dim]", "[dim]0 rows[/dim]", "[dim]—[/dim]")
    console.print(mem_tbl)
    console.print()

    # Show live SELECT output for cache
    cache_rows = conn.execute("SELECT * FROM cache").fetchall()
    cache_tbl = Table(title="SELECT * FROM cache", border_style="yellow", show_lines=True)
    cache_tbl.add_column("id", style="dim")
    cache_tbl.add_column("user_id")
    cache_tbl.add_column("question")
    cache_tbl.add_column("answer")
    cache_tbl.add_column("timestamp", style="dim")
    if cache_rows:
        for row in cache_rows:
            cache_tbl.add_row(*[str(c) for c in row])
    else:
        cache_tbl.add_row("[dim]—[/dim]", "[dim]—[/dim]", "[dim]—[/dim]", "[dim]0 rows[/dim]", "[dim]—[/dim]")
    console.print(cache_tbl)
    console.print()

    console.print(Panel(
        "[yellow]0 rows in both tables[/yellow]\n\n"
        "Run module.py and uncomment STEP 1 → STEP 2 → STEP 3 → STEP 4.\n"
        "Re-run this script any time to see rows appear.",
        border_style="yellow",
        title="Current State",
    ))
    console.print()


if __name__ == "__main__":
    setup()
