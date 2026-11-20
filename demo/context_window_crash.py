"""
demo/context_window_crash.py — Watch the context window fill up and crash.

No recovery. No Memory Manager. Just the problem.

Run:  python demo/context_window_crash.py
"""

import os
import sys
import time
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

    console.print()
    console.print(Rule("[bold]Demo — Context Window Crash[/bold]"))
    console.print()
    console.print(Panel(
        "A real conversation with Claude. No memory management.\n\n"
        "  Watch the bar fill up. When it overflows — the API crashes.\n"
        "  No recovery. The user loses everything.\n\n"
        f"[dim]Context capped at {CONTEXT_LIMIT} tokens so this happens in ~10 turns.[/dim]\n"
        f"[dim]Real Claude is 200,000 tokens — same problem, just at larger scale.[/dim]",
        border_style="red",
        title="No Memory Manager",
    ))
    console.print()
    input("  Press Enter to start...\n")

    turn_idx = 0

    while True:
        turn_idx += 1

        console.print(Rule(f"[dim]Turn {turn_idx}[/dim]", style="dim"))
        try:
            question = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            break

        messages.append({"role": "user", "content": question})
        token_counts = count_context_tokens(messages)
        pct = token_counts["total"] / CONTEXT_LIMIT

        console.print()
        render_context_bar(token_counts, turn_idx)
        time.sleep(1)

        # Simulate the crash — don't even call the API
        if pct >= CRIT_THRESHOLD:
            console.print()
            console.print(Panel(
                "[bold red]anthropic.BadRequestError: prompt is too long[/bold red]\n\n"
                f"  {token_counts['total']:,} tokens > {CONTEXT_LIMIT:,} maximum\n\n"
                "  [yellow]Agent crashed. User loses the entire conversation.[/yellow]\n"
                "  [yellow]They have to start over from scratch.[/yellow]\n\n"
                "  [dim]This is the real error. Every long-running agent hits this.[/dim]",
                border_style="red",
                title="CRASH",
            ))
            console.print()
            console.print("[dim]  (run demo/context_window_recovery.py to see the fix)[/dim]")
            console.print()
            break

        with console.status("[dim]Claude is thinking...[/dim]", spinner="dots"):
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=messages,
            )

        answer = response.content[0].text.strip()
        messages.append({"role": "assistant", "content": answer})

        console.print()
        console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
        console.print()


if __name__ == "__main__":
    run()
