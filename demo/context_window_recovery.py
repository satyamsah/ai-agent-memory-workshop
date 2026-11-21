"""
demo/context_window_recovery.py — Same conversation, with Memory Manager.

Every 5 turns: old turns compressed into a summary, deleted from context.
Context stays flat. Conversation never crashes.

Run:  python demo/context_window_recovery.py
"""

import os
import sys
import time
import sqlite3
import textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

import anthropic

load_dotenv()

console = Console()

CONTEXT_LIMIT = 1200
WARN_THRESHOLD = 0.75
CRIT_THRESHOLD = 0.90
SUMMARIZE_EVERY = 4
DB_PATH = "context_window_demo.db"

SYSTEM_PROMPT = """You are a DevCore API support agent. DevCore is a developer API platform.

Your job is to help engineers debug API integration issues quickly and accurately.

Guidelines:
- Always identify the root cause before suggesting a fix
- Reference specific HTTP error codes (401, 403, 429, 500) when relevant
- Ask clarifying questions if the issue is ambiguous
- Be concise — 2-3 sentences per response unless code is needed
- If the issue requires account changes, direct the user to dashboard.devcore.io
- Never ask for the full API key — only the last 4 characters for verification

Common issues you handle:
- Authentication errors (401): invalid or expired API keys
- Authorization errors (403): missing scopes or wrong tier
- Rate limiting (429): free tier is 10 req/sec, Pro is 100 req/sec
- Timeout errors: regional latency, suggest nearest endpoint
"""

QUESTIONS = [
    "Hi, I'm getting a 401 Unauthorized error on all my API calls.",
    "I am passing the key correctly in the Authorization header as Bearer token.",
    "The key shows as active in the dashboard. I regenerated it last week after a security warning.",
    "I updated the key in my local .env but I'm not sure about the production server.",
    "I updated it on the server and restarted. Still getting 401. Logs say 'Invalid API key format'.",
    "Fixed the newline issue. Now getting 403 Forbidden on the /data endpoint.",
    "How do I add write scope to my existing API key?",
    "Done. Now hitting 429 Too Many Requests. I'm on the free tier.",
    "My code doesn't handle 429 — it just crashes with an exception. What's the right pattern?",
    "What happens if I exceed the daily request limit on the free tier?",
    "Can I get a temporary rate limit increase while I wait for my Pro upgrade to process?",
    "Also, are there different API endpoints for different regions? I'm seeing high latency.",
]


def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def count_context_tokens(messages: list) -> dict:
    system_tokens = count_tokens(SYSTEM_PROMPT)
    conversation_tokens = sum(count_tokens(m["content"]) for m in messages)
    return {
        "system": system_tokens,
        "conversation": conversation_tokens,
        "total": system_tokens + conversation_tokens,
    }


def render_context_bar(token_counts: dict, turn: int):
    total = token_counts["total"]
    pct = total / CONTEXT_LIMIT

    if pct >= CRIT_THRESHOLD:
        color = "red"
        status = f"[bold red]{pct*100:.0f}% full — CRITICAL[/bold red]"
    elif pct >= WARN_THRESHOLD:
        color = "yellow"
        status = f"[bold yellow]{pct*100:.0f}% full — WARNING[/bold yellow]"
    else:
        color = "green"
        status = f"[green]{pct*100:.0f}% full[/green]"

    filled = int(min(pct, 1.0) * 40)
    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (40 - filled)}[/dim]"

    content = (
        f"  {bar}  {status}\n\n"
        f"  [dim]System prompt[/dim]        [dim]{token_counts['system']:,} tokens[/dim]\n"
        f"  [dim]Conversation history[/dim]  [dim]{token_counts['conversation']:,} tokens[/dim]\n"
        f"  [bold]Total[/bold]                [bold]{total:,} / {CONTEXT_LIMIT:,} tokens[/bold]"
    )

    console.print(Panel(
        content,
        title=f"[bold]Context Window — Turn {turn}[/bold]",
        border_style=color,
        padding=(0, 1),
    ))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS context_turns (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        role    TEXT NOT NULL,
        content TEXT NOT NULL,
        type    TEXT DEFAULT 'turn'
    )""")
    conn.commit()
    conn.close()


def save_turn(role: str, content: str, turn_type: str = "turn"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO context_turns (role, content, type) VALUES (?,?,?)",
        (role, content, turn_type)
    )
    conn.commit()
    conn.close()


def clear_turns():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM context_turns")
    conn.commit()
    conn.close()


def summarize_messages(client, messages: list) -> tuple[list, str]:
    turns_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                "Summarize this conversation in 3-4 sentences. "
                "Keep all key facts, errors, fixes, and decisions. "
                "Be concise — this summary replaces the full history.\n\n"
                + turns_text
            ),
        }],
    )
    summary = response.content[0].text.strip()
    compressed = [
        {"role": "user", "content": f"[Summary of earlier conversation]: {summary}"},
        {"role": "assistant", "content": "Understood, I have context from earlier. Please continue."},
    ]
    return compressed, summary


def run():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    if not api_key and not auth_token:
        console.print(Panel(
            "[bold red]✗ No Anthropic credentials found[/bold red]\n\n"
            "Set ANTHROPIC_API_KEY in .env",
            border_style="red", title="Setup Error",
        ))
        sys.exit(1)

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )
    messages = []
    init_db()
    clear_turns()  # fresh state each run

    console.print()
    console.print(Rule("[bold]Demo — Memory Manager Recovery[/bold]"))
    console.print()
    console.print(Panel(
        "Same conversation as the crash demo — but with a Memory Manager.\n\n"
        f"  Every {SUMMARIZE_EVERY} turns: old turns compressed into a summary.\n"
        "  Old turns deleted. Summary replaces them. Context drops.\n"
        "  Conversation continues — context never bursts.\n\n"
        f"[dim]Context capped at {CONTEXT_LIMIT} tokens. Real Claude is 200,000 — same pattern.[/dim]",
        border_style="green",
        title="With Memory Manager",
    ))
    console.print()
    console.print(Panel(
        "Copy-paste these one at a time:\n\n"
        + "\n".join(f"  {i+1:>2}. {q}" for i, q in enumerate(QUESTIONS)),
        border_style="dim",
        title="Questions",
    ))
    console.print()
    console.input("  Press Enter to start...")
    console.print()

    turn_idx = 0

    while True:
        turn_idx += 1

        console.print(Rule(f"[dim]Turn {turn_idx}[/dim]", style="dim"))
        try:
            question = console.input("  [bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            break

        messages.append({"role": "user", "content": question})
        save_turn("user", question)
        token_counts = count_context_tokens(messages)

        console.print()
        render_context_bar(token_counts, turn_idx)
        time.sleep(1)

        # Every SUMMARIZE_EVERY turns — compress before the API call
        if turn_idx % SUMMARIZE_EVERY == 0:
            conn = sqlite3.connect(DB_PATH)
            rows_before = conn.execute("SELECT COUNT(*) FROM context_turns").fetchone()[0]
            conn.close()

            console.print()
            console.print(Panel(
                f"[yellow]Turn {turn_idx} — Memory Manager triggered[/yellow]\n\n"
                f"  DB has [bold]{rows_before} rows[/bold] right now.\n"
                f"  Compressing → 1 summary row. All others deleted.\n\n"
                f"  [dim]Tokens before: {token_counts['total']:,}[/dim]",
                border_style="yellow",
                title="Memory Manager — Compressing",
            ))

            # Show DB before compression — students open it now
            console.print(Panel(
                f"  [bold yellow]→ Open a new terminal and run this now:[/bold yellow]\n\n"
                f"  sqlite3 context_window_demo.db \"SELECT COUNT(*) as total_rows FROM context_turns;\"\n"
                f"  sqlite3 context_window_demo.db \"SELECT * FROM context_turns;\"\n\n"
                f"  You will see [bold]{rows_before} rows[/bold] — every turn so far.\n"
                f"  Come back and press Enter — we will compress them into 1 summary row.",
                border_style="yellow",
                title="Your Turn — Query the DB",
            ))
            console.print()
            console.input("  Done? Press Enter to compress...")

            with console.status("[bold yellow]Compressing...[/bold yellow]", spinner="dots"):
                time.sleep(2)
                messages, summary = summarize_messages(client, messages)

            # Update DB — delete all turns, insert summary row
            clear_turns()
            save_turn("assistant", summary, turn_type="summary")

            conn = sqlite3.connect(DB_PATH)
            rows_after = conn.execute("SELECT COUNT(*) FROM context_turns").fetchone()[0]
            conn.close()

            new_counts = count_context_tokens(messages)
            saved = token_counts["total"] - new_counts["total"]

            console.print(Panel(
                f"[bold green]✓ Compression complete[/bold green]\n\n"
                f"  DB rows before:  [red]{rows_before}[/red]\n"
                f"  DB rows after:   [green]{rows_after}[/green]  ← 1 summary row\n\n"
                f"  Tokens before:  [red]{token_counts['total']:,}[/red]\n"
                f"  Tokens after:   [green]{new_counts['total']:,}[/green]\n"
                f"  Tokens freed:   [bold green]{saved:,}[/bold green]\n\n"
                f"  [yellow]Check the DB now:[/yellow]\n"
                f"  [bold]sqlite3 context_window_demo.db \"SELECT * FROM context_turns;\"[/bold]\n\n"
                f"  [dim]{rows_before} rows gone. {rows_after} summary row remains.[/dim]",
                title="Memory Manager — Done",
                border_style="green",
            ))
            console.print()
            console.input("  Press Enter to continue...")
            render_context_bar(new_counts, turn_idx)
            time.sleep(1)

        with console.status("[dim]Claude is thinking...[/dim]", spinner="dots"):
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=messages,
            )

        answer = response.content[0].text.strip()
        messages.append({"role": "assistant", "content": answer})
        save_turn("assistant", answer)

        console.print()
        console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
        console.print()

    console.print()
    console.print(Rule("[bold green]Demo Complete[/bold green]"))
    console.print()
    console.print(Panel(
        "[bold]What just happened:[/bold]\n\n"
        f"  • Every {SUMMARIZE_EVERY} turns — old turns compressed into a summary\n"
        "  • Old turns deleted. Summary replaced them. Context stayed flat.\n"
        "  • Agent kept full awareness — conversation never reset\n\n"
        "[bold]Key insight:[/bold]\n"
        "  YOUR CODE decides what stays in the context window.\n"
        "  Compress on a schedule — context never bursts.\n\n"
        "[dim]Next → Module 2: extract long-term memories instead of raw turns[/dim]",
        border_style="green",
        title="Summary",
    ))
    console.print()


if __name__ == "__main__":
    run()
