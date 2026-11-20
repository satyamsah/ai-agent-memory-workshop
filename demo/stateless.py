"""
demo/stateless.py — Prove that LLMs are stateless.

Two back-to-back API calls. No history passed between them.
Watch Claude forget everything from Call 1.

RUN:
  python demo/stateless.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

import anthropic

load_dotenv()

console = Console()


def call(client, messages):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        messages=messages,
    )
    return response.content[0].text.strip()


def run():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    if not api_key and not auth_token:
        console.print(Panel(
            "[red]No credentials found. Set ANTHROPIC_API_KEY in .env[/red]",
            border_style="red", title="Setup Error",
        ))
        sys.exit(1)

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )

    console.print()
    console.print(Rule("[bold]Demo — LLMs Are Stateless[/bold]"))
    console.print()

    # ── Call 1 ────────────────────────────────────────────────────────────────
    console.print("[dim]Call 1[/dim]")
    messages_1 = [{"role": "user", "content": "Hi, I'm getting a 401 error on all my API calls."}]
    console.print(f"  [bold blue]User:[/bold blue] {messages_1[0]['content']}")

    with console.status("[dim]calling Claude...[/dim]", spinner="dots"):
        reply_1 = call(client, messages_1)

    console.print(f"  [green]Claude:[/green] {reply_1}")
    console.print()

    # ── Call 2 — fresh, no history ────────────────────────────────────────────
    console.print("[dim]Call 2 — new messages list, no history passed[/dim]")
    messages_2 = [{"role": "user", "content": "Still broken. Any other ideas?"}]
    console.print(f"  [bold blue]User:[/bold blue] {messages_2[0]['content']}")

    with console.status("[dim]calling Claude...[/dim]", spinner="dots"):
        reply_2 = call(client, messages_2)

    console.print(f"  [green]Claude:[/green] {reply_2}")
    console.print()

    console.print(Panel(
        "[yellow]Claude has NO idea what 'Still broken' refers to.[/yellow]\n\n"
        "It never saw Call 1. Each API call is a fresh start.\n\n"
        "messages_1 and messages_2 are completely separate lists.\n"
        "Nothing carries over between them.\n\n"
        "[dim]This is not a bug. This is how every LLM API works.[/dim]\n\n"
        "[bold]Your code must pass the history. The LLM won't.[/bold]",
        border_style="yellow",
        title="What just happened",
    ))
    console.print()


if __name__ == "__main__":
    run()
