"""
modules/01-conversational/module.py — Conversational Memory

PROBLEM:
  LLMs are stateless. Every API call is fresh.
  Without memory, the agent forgets mid-conversation
  and knows nothing when you open a new terminal.

WHAT YOU'LL BUILD:
  Step 1 — Create a SQLite table to store conversation turns
  Step 2 — Save every turn to SQLite after the agent responds
  Step 3 — Load history from SQLite before every agent call

THE TWO-TERMINAL TEST:
  Without memory: open Terminal 2, agent has no idea who you are.
  With memory:    open Terminal 2, agent remembers your last session.

RUN:
  python modules/01-conversational/module.py
"""

import os
import sys
import sqlite3
import textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

import anthropic

load_dotenv()

console = Console()

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = "memory_workshop.db"
SESSION_ID = "alex-chen-session-1"

SYSTEM_PROMPT = """You are a DevCore API support agent. DevCore is a developer API platform.

Help engineers debug API issues. Be concise — 2-3 sentences max.
When you have context from past conversations, use it naturally.
Reference specific error codes (401, 403, 429) when relevant.
"""

# Pre-written conversation so the demo is repeatable
# Students run this, close terminal, open new terminal, run again
CONVERSATION = [
    "Hi, I'm getting a 401 Unauthorized error on all my API calls.",
    "I regenerated the key last week. It shows as active in the dashboard.",
    "Still getting 401. Any other ideas?",
    "Found it — there was a trailing newline when I copy-pasted the key.",
    "Fixed now. Thanks. I'm using the Python SDK by the way.",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Create the SQLite table for conversation turns
#
# Remove the `pass` and uncomment the function body below.
# Then re-run.
# ═══════════════════════════════════════════════════════════════════════════════

def init_db():
    pass

# def init_db():
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute("""
#         CREATE TABLE IF NOT EXISTS turns (
#             id        INTEGER PRIMARY KEY AUTOINCREMENT,
#             session   TEXT NOT NULL,
#             role      TEXT NOT NULL,
#             content   TEXT NOT NULL,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#     """)
#     conn.commit()
#     conn.close()
#     console.print("[dim]✓ SQLite table ready: turns[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Save every turn to SQLite
#
# Remove the `pass` and uncomment the function body below.
# Then re-run.
# ═══════════════════════════════════════════════════════════════════════════════

def save_turn(session: str, role: str, content: str):
    pass

# def save_turn(session: str, role: str, content: str):
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute(
#         "INSERT INTO turns (session, role, content) VALUES (?, ?, ?)",
#         (session, role, content)
#     )
#     conn.commit()
#     conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Load history before every agent call
#
# Remove the `return []` and uncomment the function body below.
# Then re-run.
# ═══════════════════════════════════════════════════════════════════════════════

def load_history(session: str, limit: int = 20) -> list:
    return []

# def load_history(session: str, limit: int = 20) -> list:
#     conn = sqlite3.connect(DB_PATH)
#     rows = conn.execute(
#         """SELECT role, content FROM turns
#            WHERE session = ?
#            ORDER BY timestamp ASC
#            LIMIT ?""",
#         (session, limit)
#     ).fetchall()
#     conn.close()
#     return [{"role": row[0], "content": row[1]} for row in rows]


# ── Agent call ────────────────────────────────────────────────────────────────

def call_agent(messages: list) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text.strip()


# ── Show memory state ─────────────────────────────────────────────────────────

def show_memory_state():
    """Show what's currently in SQLite — so students can see the DB growing."""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT session, role, content, timestamp FROM turns ORDER BY timestamp ASC"
        ).fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        console.print(Panel(
            "[yellow]SQLite is empty — no turns saved yet[/yellow]\n"
            "[dim]Uncomment STEP 1 and STEP 2 to start saving[/dim]",
            title="Memory State",
            border_style="yellow",
        ))
        return

    tbl = Table(title=f"SQLite — turns table ({len(rows)} rows)", border_style="green")
    tbl.add_column("Session", style="dim", max_width=20)
    tbl.add_column("Role", style="bold", width=10)
    tbl.add_column("Content", max_width=50)
    tbl.add_column("Time", style="dim", width=20)

    for session, role, content, timestamp in rows:
        color = "green" if role == "assistant" else "blue"
        tbl.add_row(
            session,
            f"[{color}]{role}[/{color}]",
            content[:60] + "..." if len(content) > 60 else content,
            timestamp or "",
        )
    console.print(tbl)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        console.print(Panel(
            "[red]No credentials found. Set ANTHROPIC_API_KEY in .env[/red]",
            border_style="red",
            title="Setup Error",
        ))
        sys.exit(1)

    # Initialize DB (no-op until Step 1 is uncommented)
    init_db()

    # Detect memory state
    memory_active = False
    try:
        conn = sqlite3.connect(DB_PATH)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='turns'"
        ).fetchone()
        conn.close()
        memory_active = exists is not None
    except Exception:
        pass

    console.print()
    console.print(Rule("[bold]Module 1 — Conversational Memory[/bold]"))
    console.print()

    # Show what's already in memory from previous sessions
    if memory_active:
        prev = load_history(SESSION_ID)
        if prev:
            console.print(Panel(
                f"[green]Found {len(prev)} turns from a previous session[/green]\n\n"
                "[dim]This is the two-terminal moment — the agent already knows you.[/dim]",
                border_style="green",
                title="Previous Session Loaded",
            ))
            console.print()
        else:
            console.print(Panel(
                "[green]MEMORY ACTIVE[/green] — SQLite table ready\n\n"
                "No previous session found for this user yet.\n"
                "Run through the conversation — then open a new terminal and run again.",
                border_style="green",
                title="Memory State",
            ))
            console.print()
    else:
        console.print(Panel(
            "[yellow]STATELESS MODE[/yellow] — no memory\n\n"
            "The agent gets a fresh context on every turn.\n"
            "Watch it forget on Turn 3.\n"
            "Then close this terminal, open a new one — it will know nothing.\n\n"
            "[dim]Uncomment STEP 1 → STEP 2 → STEP 3 one at a time.[/dim]",
            border_style="yellow",
            title="Current State",
        ))
        console.print()

    # Run the conversation
    for turn_num, question in enumerate(CONVERSATION, 1):
        console.print(Rule(f"[dim]Turn {turn_num}[/dim]", style="dim"))
        console.print(f"  [bold blue]User:[/bold blue] {question}")
        console.print()

        # Load history from SQLite (empty list until Step 3 is uncommented)
        history = load_history(SESSION_ID)
        messages = history + [{"role": "user", "content": question}]

        # Call agent
        with console.status("[dim]thinking...[/dim]", spinner="dots"):
            answer = call_agent(messages)

        # Save this turn (no-op until Step 2 is uncommented)
        save_turn(SESSION_ID, "user", question)
        save_turn(SESSION_ID, "assistant", answer)

        # Flag the failure moments
        if turn_num == 3 and not memory_active:
            console.print(f"  [red]Agent:[/red] {textwrap.fill(answer, 70)}")
            console.print()
            console.print(Panel(
                "[yellow]Notice:[/yellow] Did the agent ask what error you're seeing?\n"
                "It forgot you said '401' on Turn 1.\n\n"
                "[dim]Without memory — every turn is a fresh conversation.[/dim]",
                border_style="yellow",
                padding=(0, 2),
            ))
        else:
            console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")

        console.print()

    # Show memory state after conversation
    console.print(Rule("[dim]Memory State After This Session[/dim]", style="dim"))
    console.print()
    show_memory_state()
    console.print()

    console.print(Rule("[bold]End of Module 1[/bold]"))
    console.print()

    if memory_active:
        console.print(Panel(
            "[bold green]✓ Conversational memory working[/bold green]\n\n"
            "What you built:\n"
            "  • SQLite turns table — session, role, content, timestamp\n"
            "  • save_turn()    — writes every turn immediately (sync)\n"
            "  • load_history() — loads before every agent call\n\n"
            "[bold]Now do the two-terminal test:[/bold]\n"
            "  Open a new terminal and run this script again.\n"
            "  The agent will remember this entire conversation.\n\n"
            "[dim]Next → Module 2: long-term extraction + semantic cache[/dim]",
            border_style="green",
            title="Module 1 Complete",
        ))
    else:
        console.print(Panel(
            "Stateless demo complete.\n\n"
            "Now uncomment STEP 1, then STEP 2, then STEP 3.\n"
            "Re-run after each step.\n\n"
            "After all 3 steps: close this terminal, open a new one, run again.\n"
            "Watch the agent remember.",
            border_style="blue",
            title="Next Step",
        ))
    console.print()


if __name__ == "__main__":
    run()
