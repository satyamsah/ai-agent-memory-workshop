"""
demo/stateless.py — Prove that LLMs are stateless.

You type two messages. Each goes as a fresh API call — no history passed.
Watch Claude forget everything you said in the first message.

RUN:
  python demo/stateless.py
"""

import os
import sys
import textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

import anthropic

load_dotenv()

console = Console(width=80)


def call(client, messages):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        system="You are a helpful API support agent. Reply in plain text only — no markdown, no headers, no bullet points. 2 sentences max.",
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
    console.print("[dim]Type two messages. Each is a separate API call — no history passed between them.[/dim]")
    console.print()

    # ── Message 1 ─────────────────────────────────────────────────────────────
    console.print(Rule("[dim]Call 1[/dim]", style="dim"))
    console.print("[dim]  Suggested: 'I am getting a 401 error while calling the GitHub API'[/dim]")
    msg1 = console.input("  [bold blue]You:[/bold blue] ").strip()
    if not msg1:
        msg1 = "I am getting a 401 error while calling the GitHub API."
        console.print(f"  [dim](using: {msg1})[/dim]")

    with console.status("[dim]calling Claude...[/dim]", spinner="dots"):
        reply1 = call(client, [{"role": "user", "content": msg1}])

    console.print(f"  [green]Claude:[/green] {textwrap.fill(reply1, 70)}")
    console.print()

    # ── Message 2 — fresh call, history NOT passed ─────────────────────────
    console.print(Rule("[dim]Call 2 — fresh API call, no history[/dim]", style="dim"))
    console.print("[dim]  (say something that only makes sense if Claude remembers Call 1)[/dim]")
    msg2 = console.input("  [bold blue]You:[/bold blue] ").strip()
    if not msg2:
        msg2 = "Still broken. Any other ideas?"
        console.print(f"  [dim](using: {msg2})[/dim]")

    with console.status("[dim]calling Claude...[/dim]", spinner="dots"):
        reply2 = call(client, [{"role": "user", "content": msg2}])

    console.print(f"  [green]Claude:[/green] {textwrap.fill(reply2, 70)}")
    console.print()

    console.print(Panel(
        "[yellow]Claude has no idea what you said in Call 1.[/yellow]\n\n"
        "Each call gets its own fresh messages list.\n"
        "Nothing carries over — not even from one line above.\n\n"
        "[dim]This is not a bug. This is how every LLM API works.[/dim]\n\n"
        "[bold]Your code must pass the history. The LLM won't.[/bold]",
        border_style="yellow",
        title="What just happened",
    ))
    console.print()


if __name__ == "__main__":
    run()
