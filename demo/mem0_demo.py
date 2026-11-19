"""
demo/mem0_demo.py — The same system you just built, in ~20 lines.

You built:
  - SQLite for facts + episodic
  - FAISS for understanding
  - LLM extraction after each turn
  - Semantic cache
  - Memory Manager routing

Mem0 (69k GitHub stars) does all of that for you.
Same architecture. Same pattern. Now you know what's inside.

RUN:
  python demo/mem0_demo.py

REQUIRES:
  pip install mem0ai   (already in requirements.txt)
  ANTHROPIC_API_KEY in .env
"""

import os
import sys
import shutil
import textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

import anthropic

load_dotenv()

console = Console()

USER_ID = "alex-chen-mem0"

SYSTEM_PROMPT = """You are a DevCore API support agent.
Help engineers debug API issues. Be concise — 2-3 sentences max.
Only reference past interactions when directly relevant to what the user just asked.
"""

# Same conversation as Module 3 — so students can compare directly
SESSIONS = {
    "Session 1 — Alex reports a 401 issue": [
        "Hi, I need some help with my API.",
        "I'm getting a 401 Unauthorized error on all my calls.",
        "Found it — there was a trailing newline when I copy-pasted the key.",
        "Fixed now. I'm using the Python SDK by the way.",
    ],
    "Session 2 — Alex comes back (new terminal)": [
        "Hi, I need some help.",
        "I'm getting a 401 error again on my API calls.",
        "What do I usually get wrong when setting up credentials?",
        "What tier am I on?",
        "What's the rate limit on the free tier?",
        "What's the rate limit on the free tier?",
    ],
}


def build_mem0():
    """Initialize Mem0 with Claude Haiku + FAISS — no Docker needed."""
    from mem0 import Memory

    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")

    config = {
        "llm": {
            "provider": "anthropic",
            "config": {
                "model": "claude-haiku-4-5-20251001",
                "api_key": api_key or auth_token,
                "temperature": 0.1,
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
            },
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "path": os.path.join(os.path.dirname(os.path.dirname(__file__)), "mem0_faiss_store"),
                "embedding_model_dims": 384,  # all-MiniLM-L6-v2 outputs 384 dims (not OpenAI's 1536)
            },
        },
    }

    return Memory.from_config(config)


def call_agent(messages: list, memories: list) -> str:
    """Call Claude with conversation history + retrieved memories as context."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )

    # Inject memories as context only if relevant ones were retrieved
    full_messages = list(messages)
    if memories:
        memory_text = "\n".join(f"  • {m['memory']}" for m in memories)
        full_messages.insert(0, {
            "role": "user",
            "content": f"[Relevant context from memory]\n{memory_text}"
        })
        full_messages.insert(1, {
            "role": "assistant",
            "content": "Understood, I have relevant context about this user."
        })

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=full_messages,
    )
    return response.content[0].text.strip()


def show_memories(mem0_client, user_id: str):
    """Show all memories Mem0 extracted for this user."""
    try:
        all_memories = mem0_client.get_all(filters={"user_id": user_id})
        memories = all_memories.get("results", all_memories) if isinstance(all_memories, dict) else all_memories
        if not memories:
            console.print("[dim]  No memories extracted yet[/dim]")
            console.print()
            return

        tbl = Table(title=f"Mem0 Memories for {user_id}", border_style="green")
        tbl.add_column("#", width=4, style="dim")
        tbl.add_column("Memory", max_width=70)

        for i, m in enumerate(memories, 1):
            content = m.get("memory", str(m))
            tbl.add_row(str(i), content)

        console.print(tbl)
        console.print()
    except Exception as e:
        console.print(f"[dim]  Could not load memories: {e}[/dim]")
        console.print()


def run():
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        console.print(Panel(
            "[red]No credentials found. Set ANTHROPIC_API_KEY in .env[/red]",
            border_style="red",
            title="Setup Error",
        ))
        sys.exit(1)

    # Clear any previous demo state so FAISS dimensions are consistent
    store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mem0_faiss_store")
    if os.path.exists(store_path):
        shutil.rmtree(store_path)

    console.print()
    console.print(Rule("[bold]Demo — Mem0: Industry-Standard Agent Memory[/bold]"))
    console.print()
    console.print(Panel(
        "You just built memory management from scratch:\n"
        "  • SQLite for facts + episodic memories\n"
        "  • FAISS for understanding/patterns\n"
        "  • LLM extraction after each turn\n"
        "  • Semantic cache\n"
        "  • Memory Manager routing\n\n"
        "[bold]Mem0 has 69,000 GitHub stars.[/bold]\n"
        "It does all of that for you.\n\n"
        "Watch the same system run — now you know what's inside.",
        border_style="blue",
        title="What You Built vs Mem0",
    ))
    console.print()

    # Initialize Mem0
    with console.status("[dim]Initializing Mem0 with Claude Haiku + FAISS...[/dim]", spinner="dots"):
        try:
            mem0 = build_mem0()
        except Exception as e:
            console.print(Panel(
                f"[red]Failed to initialize Mem0:[/red] {e}\n\n"
                "Make sure mem0ai is installed:\n"
                "  pip install mem0ai",
                border_style="red",
                title="Mem0 Error",
            ))
            sys.exit(1)

    console.print("[green]✓ Mem0 initialized — Claude Haiku + FAISS[/green]")
    console.print()

    # Run both sessions
    for session_name, turns in SESSIONS.items():
        console.print(Rule(f"[bold]{session_name}[/bold]"))
        console.print()

        messages = []

        for turn_num, question in enumerate(turns, 1):
            console.print(f"  [bold blue]User:[/bold blue] {question}")

            # ── Mem0: search relevant memories ────────────────────────────
            # This is what you built in route_reads()
            with console.status("[dim]searching memory...[/dim]", spinner="dots"):
                try:
                    search_results = mem0.search(question, user_id=USER_ID, limit=3)
                    memories = search_results.get("results", search_results) if isinstance(search_results, dict) else search_results
                    memories = memories or []
                except Exception:
                    memories = []

            if memories:
                console.print(f"  [dim]Mem0 retrieved {len(memories)} relevant memor{'y' if len(memories)==1 else 'ies'}:[/dim]")
                for m in memories:
                    content = m.get("memory", str(m))
                    console.print(f"  [dim]  → {content}[/dim]")

            # ── Build messages + call agent ────────────────────────────────
            messages.append({"role": "user", "content": question})
            answer = call_agent(messages, memories)
            messages.append({"role": "assistant", "content": answer})

            console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
            console.print()

            # ── Mem0: add this turn to memory ──────────────────────────────
            # This is what you built in route_writes() + extract_memories()
            with console.status("[dim]Mem0 extracting memories...[/dim]", spinner="dots"):
                try:
                    turn_messages = [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                    mem0.add(turn_messages, user_id=USER_ID)
                except Exception:
                    pass

        # Show what Mem0 remembers after this session
        console.print(Rule("[dim]What Mem0 Remembers After This Session[/dim]", style="dim"))
        console.print()
        show_memories(mem0, USER_ID)

    console.print(Rule("[bold green]Demo Complete[/bold green]"))
    console.print()
    console.print(Panel(
        "[bold]What Mem0 did under the hood — same as what you built:[/bold]\n\n"
        "  1. After each turn → LLM extracted facts, episodic events, patterns\n"
        "  2. Stored in vector DB (FAISS) with metadata\n"
        "  3. On each turn → semantic search retrieved relevant memories\n"
        "  4. Memories injected into context only when relevant\n"
        "  5. Session 2 remembered Session 1 — cross-session memory\n\n"
        "[bold]The difference:[/bold]\n"
        "  You wrote ~300 lines. Mem0 is 2 lines.\n"
        "  But now you understand every line inside Mem0.\n\n"
        "[dim]That's the point of this workshop.[/dim]",
        border_style="green",
        title="Summary",
    ))
    console.print()


if __name__ == "__main__":
    run()
