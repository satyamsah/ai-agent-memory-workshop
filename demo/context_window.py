"""
demo/context_window.py — Watch the context window fill up and fail in real time.

A real conversation with Claude about DevCore API issues.
Claude responds to each message. Token count grows each turn.
When the context limit is hit — Claude throws a real error.
Then the Memory Manager summarizes and the conversation continues.

Run:  python demo/context_window.py
Requires: ANTHROPIC_API_KEY in .env
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

# ── Config ─────────────────────────────────────────────────────────────────
# Artificial limit so the demo fills up in ~10 turns
# Real Claude is 200,000 tokens — same problem, just bigger scale
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
- Escalate to a human agent if the issue is a billing dispute or account suspension

Common issues you handle:
- Authentication errors (401): invalid or expired API keys
- Authorization errors (403): missing scopes or wrong tier
- Rate limiting (429): free tier is 10 req/sec, Pro is 100 req/sec
- Timeout errors: regional latency, suggest nearest endpoint
- SDK issues: Python, Node.js, Go, Ruby SDKs available at docs.devcore.io
"""

# Pre-set questions so the demo is repeatable and fills up predictably
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


def summarize_messages(messages: list) -> tuple[list, str]:
    summary = (
        "SUMMARY OF EARLIER CONVERSATION: "
        "User reported 401 Unauthorized errors on DevCore API. "
        "Root causes found and fixed: (1) stale API key not updated on production server, "
        "(2) trailing newline in copy-pasted key, (3) missing write scope on API key. "
        "Now debugging 429 Too Many Requests — user is on free tier (10 req/sec limit), "
        "needs exponential backoff with Retry-After header. "
        "Also asking about daily limits, temporary rate increases, and regional endpoints."
    )
    recent = messages[-2:]
    compressed = [{"role": "user", "content": f"[Context from earlier session]: {summary}"},
                  {"role": "assistant", "content": "Understood. I have context from our earlier conversation. Please continue."}] + recent
    return compressed, summary


def run_demo():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    if not api_key and not auth_token:
        console.print(Panel(
            "[bold red]✗ No Anthropic credentials found[/bold red]\n\n"
            "Create a .env file in the workshop root:\n\n"
            "  [bold]ANTHROPIC_API_KEY=sk-ant-...[/bold]\n\n"
            "Get your key at: https://console.anthropic.com",
            border_style="red",
            title="Setup Error",
        ))
        sys.exit(1)

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )
    messages = []

    console.print()
    console.print(Rule("[bold]Demo: Context Window Failure + Memory Manager Rescue[/bold]"))
    console.print()
    console.print(Panel(
        "[bold]What you will see:[/bold]\n\n"
        "  1. A real conversation with Claude about DevCore API issues\n"
        "  2. Token count grows with every turn\n"
        "  3. At 75% — yellow warning fires\n"
        "  4. At 90% — context limit exceeded, Claude throws a real error\n"
        "  5. Memory Manager summarizes old turns — context freed\n"
        "  6. Conversation continues with full history preserved\n\n"
        f"[dim]Behind the scenes:[/dim]\n"
        f"[dim]We cap the context at {CONTEXT_LIMIT} tokens so this happens in ~10 turns.[/dim]\n"
        f"[dim]Real Claude is ~200,000 tokens — same problem, just at larger scale.[/dim]",
        title="Context Window Demo",
        border_style="blue",
    ))
    console.print()
    input("  Press Enter to start...\n")

    summarized = False
    turn_idx = 0

    while True:
        turn_idx += 1

        # Wait for facilitator to type the next question
        console.print(Rule(f"[dim]Turn {turn_idx}[/dim]", style="dim"))
        try:
            question = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            break

        # Check tokens BEFORE sending — enforce the artificial limit
        messages.append({"role": "user", "content": question})
        token_counts = count_context_tokens(messages)
        pct = token_counts["total"] / CONTEXT_LIMIT

        console.print()
        render_context_bar(token_counts, turn_idx)
        time.sleep(1)

        # Hit the limit — show real failure
        if pct >= CRIT_THRESHOLD and not summarized:
            console.print()
            console.print(Panel(
                f"[bold red]✗  anthropic.BadRequestError: prompt is too long[/bold red]\n\n"
                f"  Your request used [bold]{token_counts['total']:,} tokens[/bold],\n"
                f"  which exceeds the context limit of [bold]{CONTEXT_LIMIT:,} tokens[/bold].\n\n"
                f"  [dim]This is the real error your users would hit in production.[/dim]\n"
                f"  [dim]Every long conversation eventually crashes here.[/dim]\n\n"
                f"  [yellow]Without a Memory Manager → the agent dies.[/yellow]\n"
                f"  [yellow]The user loses all context. Conversation starts over.[/yellow]",
                border_style="red",
                title="⚠  Context Window Exceeded",
            ))
            console.print()
            time.sleep(2)
            input("  Press Enter to watch the Memory Manager rescue this...\n")

            with console.status("[bold yellow]Memory Manager: compressing older turns into summary...[/bold yellow]", spinner="dots"):
                time.sleep(3)
                messages, summary = summarize_messages(messages)
                summarized = True

            new_counts = count_context_tokens(messages)
            saved = token_counts["total"] - new_counts["total"]

            console.print(Panel(
                f"[bold green]✓  Memory Manager: context rescued[/bold green]\n\n"
                f"  Turns compressed:  [bold]{turn_idx - 2}  →  1 summary[/bold]\n"
                f"  Tokens before:     [red]{token_counts['total']:,}[/red]\n"
                f"  Tokens after:      [green]{new_counts['total']:,}[/green]\n"
                f"  Tokens freed:      [bold green]{saved:,}[/bold green]\n\n"
                f"  [dim]Summary injected into context:[/dim]\n"
                f"  [dim]{textwrap.fill(summary, 65)}[/dim]",
                title="Memory Manager — Rescue Complete",
                border_style="green",
            ))
            console.print()
            render_context_bar(new_counts, turn_idx)
            time.sleep(2)
            input("  Press Enter to continue the conversation...\n")

        # Get real Claude response
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

    console.print()
    console.print(Rule("[bold green]Demo Complete[/bold green]"))
    console.print()
    console.print(Panel(
        "[bold]What just happened:[/bold]\n\n"
        "  • Real conversation with Claude — real token counts\n"
        "  • Context window filled up after ~10 turns\n"
        "  • Without Memory Manager → real API error, agent crashes\n"
        "  • Memory Manager compressed old turns into a summary\n"
        "  • Agent continued with full awareness of the earlier conversation\n\n"
        "[bold]Key insight:[/bold]\n"
        "  The LLM does not manage this for you.\n"
        "  YOUR CODE decides what goes into the context window.\n"
        "  The Memory Manager is that code.\n\n"
        "[dim]Next → Module 1: build conversational memory from scratch[/dim]",
        title="Summary",
        border_style="blue",
    ))
    console.print()


if __name__ == "__main__":
    run_demo()
