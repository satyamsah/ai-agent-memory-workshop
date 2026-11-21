"""
demo/mem0_session2.py — Session 2: Alex comes back. Mem0 remembers.

RUN AFTER mem0_session1.py (in a new terminal):
  python demo/mem0_session2.py
"""

import os
import sys
import warnings
import logging
import textwrap
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
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
If the conversation includes relevant context from memory, treat it as ground truth and use it to answer directly.
Only reference past interactions when directly relevant to what the user just asked.
"""

TURNS = [
    "Hi, I need some help.",
    "I'm getting a 401 error again on my API calls.",
    "What do I usually get wrong when setting up credentials?",
    "What plan is my DevCore account on?",
]


def build_mem0():
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
            "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mem0_faiss_store"),
                "embedding_model_dims": 384,
            },
        },
    }
    return Memory.from_config(config)


def call_agent(messages: list, memories: list) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )

    system = SYSTEM_PROMPT
    if memories:
        memory_text = "\n".join(f"  • {m['memory']}" for m in memories)
        system += f"\n\nKnown facts about this user (treat as ground truth):\n{memory_text}"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()


def show_memories(mem0_client):
    try:
        all_memories = mem0_client.get_all(filters={"user_id": USER_ID})
        memories = all_memories.get("results", all_memories) if isinstance(all_memories, dict) else all_memories
        if not memories:
            console.print("[dim]  No memories found[/dim]")
            console.print()
            return

        tbl = Table(title=f"Mem0 memories for {USER_ID}", border_style="green")
        tbl.add_column("#", width=4, style="dim")
        tbl.add_column("Memory", max_width=70)
        for i, m in enumerate(memories, 1):
            tbl.add_row(str(i), m.get("memory", str(m)))
        console.print(tbl)
        console.print()
    except Exception as e:
        console.print(f"[dim]  Could not load memories: {e}[/dim]")
        console.print()


def run():
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        console.print(Panel("[red]No credentials found. Set ANTHROPIC_API_KEY in .env[/red]", border_style="red", title="Setup Error"))
        sys.exit(1)

    with console.status("[dim]Initializing Mem0...[/dim]", spinner="dots"):
        try:
            mem0 = build_mem0()
        except Exception as e:
            console.print(Panel(f"[red]Failed to initialize Mem0:[/red] {e}", border_style="red", title="Mem0 Error"))
            sys.exit(1)

    console.print()
    console.print(Rule("[bold]Mem0 Demo — Session 2[/bold]"))
    console.print()

    # Show what Mem0 already knows before the conversation starts
    console.print("[dim]Memories loaded from Session 1:[/dim]")
    show_memories(mem0)

    console.print(Panel(
        "New terminal. New process. Alex hasn't said anything yet.\n\n"
        "Watch Mem0 retrieve memories from Session 1 on every turn —\n"
        "the agent already knows about the trailing newline, the Python SDK, and more.",
        border_style="green",
        title="Cross-session memory",
    ))
    console.print()
    console.print(Panel(
        "Suggested questions — copy-paste one at a time:\n\n"
        + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(TURNS))
        + "\n\n[dim]Type 'quit' to stop.[/dim]",
        border_style="dim",
        title="Try These",
    ))
    console.print()

    messages = []
    turn_num = 0

    while True:
        turn_num += 1
        console.print(Rule(f"[dim]Turn {turn_num}[/dim]", style="dim"))
        if turn_num <= len(TURNS):
            console.print(f"  [dim]Hint: {TURNS[turn_num - 1]}[/dim]")
        console.print()

        try:
            question = console.input("  [bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            turn_num -= 1
            continue
        if question.lower() in ("quit", "exit", "q"):
            break

        with console.status("[dim]searching memory...[/dim]", spinner="dots"):
            try:
                search_results = mem0.search(question, filters={"user_id": USER_ID}, limit=3)
                memories = search_results.get("results", search_results) if isinstance(search_results, dict) else search_results
                memories = memories or []
                if not memories:
                    all_results = mem0.get_all(filters={"user_id": USER_ID})
                    all_mems = all_results.get("results", all_results) if isinstance(all_results, dict) else all_results
                    memories = all_mems or []
            except Exception:
                memories = []

        if memories:
            console.print(f"  [dim]Mem0 retrieved {len(memories)} memor{'y' if len(memories)==1 else 'ies'}:[/dim]")
            for m in memories:
                console.print(f"  [dim]  → {m.get('memory', str(m))}[/dim]")
        else:
            console.print(f"  [dim]Mem0: 0 memories retrieved[/dim]")

        messages.append({"role": "user", "content": question})
        answer = call_agent(messages, memories)
        messages.append({"role": "assistant", "content": answer})

        console.print()
        console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
        console.print()

        with console.status("[dim]Mem0 extracting memories...[/dim]", spinner="dots"):
            try:
                mem0.add([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ], user_id=USER_ID)
            except Exception:
                pass

        console.print(Rule(style="dim"))
        console.print()

    console.print(Rule("[bold green]Session 2 complete[/bold green]"))
    console.print()
    console.print(Panel(
        "[bold]What Mem0 did — same as what you built in Module 2:[/bold]\n\n"
        "  1. After each turn → LLM extracted facts and episodic events\n"
        "  2. Stored in FAISS vector store\n"
        "  3. Each turn → semantic search retrieved relevant memories\n"
        "  4. Memories injected into system prompt\n"
        "  5. Session 2 remembered Session 1 — cross-session memory\n\n"
        "[bold]The difference:[/bold]\n"
        "  You wrote ~300 lines. Mem0 is 2 lines.\n"
        "  But now you understand every line inside Mem0.",
        border_style="green",
        title="Summary",
    ))
    console.print()


if __name__ == "__main__":
    run()
