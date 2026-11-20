"""
modules/03-memory-manager/module.py — Memory Manager Routing

PROBLEM:
  You now have three memory stores:
    - SQLite: conversation turns (this session)
    - SQLite: facts + episodic (long-term)
    - FAISS:  understanding/patterns (long-term)

  Loading all of them on every turn is slow, noisy, and breaks context.
  "What plan is my DevCore account on?" doesn't need FAISS.
  "What do I usually get wrong?" doesn't need an exact SQL row.
  "Hi" doesn't need any memory at all.

WHAT YOU'LL BUILD:
  Step 1 — Route reads: decide WHICH memory to load per query
  Step 2 — Route writes: decide WHAT to save and WHERE after each turn
  Step 3 — Full loop: read → respond → write → next turn

THE KEY RULE:
  Only surface past memory when the query signals it's needed.
  "I have a 401 again" → check episodic history → relevant
  "Hi" → no memory injection → just respond

RUN:
  python modules/03-memory-manager/module.py
"""

import os
import sys
import json
import sqlite3
import textwrap
from datetime import datetime
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
USER_ID = "alex-chen"
SESSION_ID = f"{USER_ID}-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
FAISS_PATH = "memory_faiss"

SYSTEM_PROMPT = """You are a DevCore API support agent. DevCore is a developer API platform.

Help engineers debug API issues. Be concise — 2-3 sentences max.
Only reference past interactions when they are directly relevant to what the user just asked.
Do not volunteer that you have memory of the user unless it helps answer their question.
Reference specific error codes (401, 403, 429) when relevant.
"""

EXTRACTION_PROMPT = """You are a memory extractor. Read this conversation turn and extract memories worth keeping.

Return a JSON object with this exact structure:
{
  "facts": ["fact1", "fact2"],
  "episodic": ["event1"],
  "understanding": ["pattern1"]
}

facts: Simple facts about the user. "Alex uses Python SDK", "Alex is on free tier"
episodic: Specific events. "Alex had 401 caused by trailing newline in copy-pasted key"
understanding: Patterns observed across signals. "Alex makes copy-paste errors with credentials"

Rules:
- Only extract clear signal. Empty lists are fine.
- Do not extract from generic advice or agent responses.
- Do not write understanding from a single weak signal.
- Return valid JSON only.

User: {user_message}
Agent: {agent_message}

Existing memories:
{existing_memories}
"""

# Conversation designed to test all routing paths:
# - Turn 1: generic greeting → no memory needed
# - Turn 2: 401 error again → route to episodic
# - Turn 3: "what do I usually get wrong" → route to understanding (FAISS)
# - Turn 4: "what plan is my DevCore account on" → route to facts (SQL)
# - Turn 5: rate limit question → cache check first
# - Turn 6: same rate limit question → cache hit
CONVERSATION = [
    "Hi, I need some help.",
    "I'm getting a 401 error again on my API calls.",
    "What do I usually get wrong when setting up credentials?",
    "What plan is my DevCore account on?",
    "What's the rate limit on the free tier?",
    "What's the rate limit on the free tier?",   # cache hit
]


# ── Database helpers (fully built — not part of the student exercise) ─────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session TEXT NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, type TEXT NOT NULL,
        content TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, question TEXT NOT NULL,
        answer TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()


def save_turn(session, role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO turns (session, role, content) VALUES (?,?,?)", (session, role, content))
    conn.commit()
    conn.close()


def load_recent_turns(session, limit=6):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM turns WHERE session=? ORDER BY timestamp ASC LIMIT ?",
        (session, limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


def load_facts(user_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT content FROM memories WHERE user_id=? AND type='fact' ORDER BY timestamp ASC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def load_episodic(user_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT content FROM memories WHERE user_id=? AND type='episodic' ORDER BY timestamp DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def load_understanding(query, k=2):
    if not os.path.exists(FAISS_PATH):
        return []
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        store = FAISS.load_local(FAISS_PATH, embedder, allow_dangerous_deserialization=True)
        docs = store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
    except Exception:
        return []


def check_cache(user_id, question, threshold=0.85):
    cache_path = f"cache_faiss_{user_id}"
    if not os.path.exists(cache_path):
        return None
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        store = FAISS.load_local(cache_path, embedder, allow_dangerous_deserialization=True)
        results = store.similarity_search_with_score(question, k=1)
        if results and results[0][1] < (1 - threshold):
            cached_q = results[0][0].page_content
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT answer FROM cache WHERE user_id=? AND question=? LIMIT 1",
                (user_id, cached_q)
            ).fetchone()
            conn.close()
            return row[0] if row else None
    except Exception:
        return None


def save_to_cache(user_id, question, answer):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO cache (user_id, question, answer) VALUES (?,?,?)",
        (user_id, question, answer)
    )
    conn.commit()
    conn.close()
    cache_path = f"cache_faiss_{user_id}"
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        if os.path.exists(cache_path):
            store = FAISS.load_local(cache_path, embedder, allow_dangerous_deserialization=True)
            store.add_texts([question])
        else:
            store = FAISS.from_texts([question], embedder)
        store.save_local(cache_path)
    except Exception:
        pass


def save_memory(user_id, mem_type, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memories (user_id, type, content) VALUES (?,?,?)",
        (user_id, mem_type, content)
    )
    conn.commit()
    conn.close()


def extract_memories(user_id, user_msg, agent_msg):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    client = anthropic.Anthropic(
        api_key=api_key or "dummy",
        auth_token=auth_token if not api_key else None,
        base_url=base_url,
    )
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT type, content FROM memories WHERE user_id=? ORDER BY timestamp ASC",
        (user_id,)
    ).fetchall()
    conn.close()
    existing = "\n".join(f"[{r[0]}] {r[1]}" for r in rows) or "None yet"

    prompt = EXTRACTION_PROMPT.format(
        user_message=user_msg,
        agent_message=agent_msg,
        existing_memories=existing,
    )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        extracted = json.loads(response.content[0].text.strip())
    except Exception:
        return

    saved = []
    for f in extracted.get("facts", []):
        save_memory(user_id, "fact", f)
        saved.append(("cyan", "fact", f))
    for e in extracted.get("episodic", []):
        save_memory(user_id, "episodic", e)
        saved.append(("yellow", "episodic", e))
    for p in extracted.get("understanding", []):
        # Save understanding to FAISS
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_huggingface import HuggingFaceEmbeddings
            embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            if os.path.exists(FAISS_PATH):
                store = FAISS.load_local(FAISS_PATH, embedder, allow_dangerous_deserialization=True)
                store.add_texts([p])
            else:
                store = FAISS.from_texts([p], embedder)
            store.save_local(FAISS_PATH)
        except Exception:
            pass
        saved.append(("magenta", "understanding", p))

    for color, label, content in saved:
        console.print(f"  [dim]→ [{color}]{label}[/{color}]: {content}[/dim]")


def call_agent(messages):
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


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Route reads: decide which memory to load per query
#
# This is the routing brain. For each query, decide:
#   - Does this reference a past error/issue? → load episodic
#   - Does this ask about a pattern/tendency? → load understanding (FAISS)
#   - Does this ask about a specific fact?    → load facts (SQL)
#   - Is this a generic question?             → load nothing personal
#
# Remove the stub and uncomment the routing logic below.
# ═══════════════════════════════════════════════════════════════════════════════

def route_reads(query: str, user_id: str) -> dict:
    """Decide which memory to load for this query. Returns context dict."""
    return {"facts": [], "episodic": [], "understanding": [], "history": []}

# def route_reads(query: str, user_id: str) -> dict:
#     result = {"facts": [], "episodic": [], "understanding": [], "history": []}
#     q = query.lower()
#
#     # Always load recent conversation turns from this session
#     result["history"] = load_recent_turns(SESSION_ID)
#
#     # Load episodic when user references a past event or recurring issue
#     if any(kw in q for kw in [
#         "again", "before", "last time", "same issue", "previously",
#         "still", "another", "keep getting", "always"
#     ]):
#         result["episodic"] = load_episodic(user_id)
#
#     # Load understanding when user asks about patterns or tendencies
#     if any(kw in q for kw in [
#         "usually", "tend to", "always", "pattern", "wrong",
#         "mistake", "typically", "often"
#     ]):
#         result["understanding"] = load_understanding(query)
#
#     # Load facts when user asks about their account or setup
#     if any(kw in q for kw in [
#         "tier", "plan", "sdk", "account", "my ", "am i", "do i"
#     ]):
#         result["facts"] = load_facts(user_id)
#
#     return result


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Route writes: decide what to save and where after each turn
#
# Remove the stub and uncomment the write routing logic below.
# ═══════════════════════════════════════════════════════════════════════════════

def route_writes(query: str, answer: str, user_id: str, session: str):
    """Decide what to save after this turn."""
    pass

# def route_writes(query: str, answer: str, user_id: str, session: str):
#     # Always save the turn to conversational memory
#     save_turn(session, "user", query)
#     save_turn(session, "assistant", answer)
#
#     # Always save to semantic cache
#     save_to_cache(user_id, query, answer)
#
#     # Extract and save facts, episodic, understanding asynchronously
#     # (In production: run this in a background thread)
#     extract_memories(user_id, query, answer)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Build the context window from routed memory
#
# Remove the stub and uncomment the context builder below.
# ═══════════════════════════════════════════════════════════════════════════════

def build_context(memory: dict, question: str) -> list:
    """Build the messages list from routed memory."""
    return [{"role": "user", "content": question}]

# def build_context(memory: dict, question: str) -> list:
#     messages = []
#
#     # Inject relevant memory as context — only what was routed
#     context_parts = []
#
#     if memory["facts"]:
#         context_parts.append("Facts about this user:\n" +
#             "\n".join(f"  • {f}" for f in memory["facts"]))
#
#     if memory["episodic"]:
#         context_parts.append("Past issues for this user:\n" +
#             "\n".join(f"  • {e}" for e in memory["episodic"]))
#
#     if memory["understanding"]:
#         context_parts.append("Patterns observed about this user:\n" +
#             "\n".join(f"  • {u}" for u in memory["understanding"]))
#
#     if context_parts:
#         messages.append({
#             "role": "user",
#             "content": "[Relevant context from memory]\n\n" + "\n\n".join(context_parts)
#         })
#         messages.append({
#             "role": "assistant",
#             "content": "Understood, I have relevant context."
#         })
#
#     # Add conversation history
#     messages += memory["history"]
#
#     # Add current question
#     messages.append({"role": "user", "content": question})
#     return messages


# ── Main ──────────────────────────────────────────────────────────────────────

def show_routing_decision(memory: dict, cache_hit: bool):
    """Show what the Memory Manager decided to load."""
    tbl = Table(show_header=False, box=None, padding=(0, 2))
    tbl.add_column("", style="dim")
    tbl.add_column("")

    if cache_hit:
        tbl.add_row("routing:", "[cyan]cache hit — skipping all memory[/cyan]")
    else:
        tbl.add_row("history turns:", str(len(memory.get("history", []))))
        tbl.add_row("facts loaded:", str(len(memory.get("facts", []))))
        tbl.add_row("episodic loaded:", str(len(memory.get("episodic", []))))
        tbl.add_row("understanding loaded:", str(len(memory.get("understanding", []))))

    console.print(tbl)


def run():
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_AUTH_TOKEN"):
        console.print(Panel(
            "[red]No credentials found. Set ANTHROPIC_API_KEY in .env[/red]",
            border_style="red",
            title="Setup Error",
        ))
        sys.exit(1)

    init_db()

    console.print()
    console.print(Rule("[bold]Module 3 — Memory Manager[/bold]"))
    console.print()

    # Check if routing is active
    test_memory = route_reads("test", USER_ID)
    routing_active = "history" in test_memory and isinstance(test_memory["history"], list)
    # Routing is only truly active when the student has uncommented the logic
    # We detect this by checking if episodic routing keyword triggers a load
    routing_active = False  # Will be True after Step 1 is uncommented

    console.print(Panel(
        "[yellow]NO ROUTING[/yellow] — all memory loaded on every turn (or none)\n\n"
        "Watch the agent answer without past context.\n"
        "Turn 2 references 'again' — without routing, no episodic memory loads.\n\n"
        "[dim]Uncomment STEP 1 → STEP 2 → STEP 3[/dim]"
        if not routing_active else
        "[green]MEMORY MANAGER ACTIVE[/green] — routing reads and writes per query",
        border_style="yellow" if not routing_active else "green",
        title="Current State",
    ))
    console.print()

    for turn_num, question in enumerate(CONVERSATION, 1):
        console.print(Rule(f"[dim]Turn {turn_num}[/dim]", style="dim"))
        console.print(f"  [bold blue]User:[/bold blue] {question}")
        console.print()

        # ── Check cache first ──────────────────────────────────────────────
        cached = check_cache(USER_ID, question)
        if cached:
            console.print(f"  [dim]Memory Manager →[/dim]")
            show_routing_decision({}, cache_hit=True)
            console.print()
            console.print(f"  [bold cyan]⚡ Cache HIT[/bold cyan] — 0 tokens, 0ms LLM latency")
            console.print(f"  [green]Agent:[/green] {textwrap.fill(cached, 70)}")
            console.print()
            continue

        # ── Route: decide what memory to load ─────────────────────────────
        memory = route_reads(question, USER_ID)

        # Show routing decision
        console.print(f"  [dim]Memory Manager →[/dim]")
        show_routing_decision(memory, cache_hit=False)
        console.print()

        # ── Build context from routed memory ───────────────────────────────
        messages = build_context(memory, question)

        # ── Call agent ─────────────────────────────────────────────────────
        with console.status("[dim]thinking...[/dim]", spinner="dots"):
            answer = call_agent(messages)

        # ── Route writes: save turn + extract memories ─────────────────────
        route_writes(question, answer, USER_ID, SESSION_ID)

        console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
        console.print()

    console.print(Rule("[bold]End of Module 3[/bold]"))
    console.print()
    console.print(Panel(
        "What you built:\n\n"
        "  • route_reads()   — decides which memory to load per query\n"
        "  • route_writes()  — saves turns + extracts memories after each turn\n"
        "  • build_context() — assembles the context window from routed memory\n\n"
        "[bold]Key rule:[/bold]\n"
        "  Only surface past memory when the query signals it's needed.\n"
        "  'I have a 401 again' → load episodic\n"
        "  'What do I usually get wrong?' → load understanding\n"
        "  'Hi' → load nothing personal\n\n"
        "[dim]Next → Demo: Mem0 does all of this in 5 lines[/dim]",
        border_style="green" if routing_active else "blue",
        title="Module 3 Complete" if routing_active else "Next Step",
    ))
    console.print()


if __name__ == "__main__":
    run()
