"""
modules/02-extraction/module.py — Long-term Memory Extraction + Semantic Cache

PROBLEM:
  Module 1 saves every word of every conversation.
  After 1000 turns across 10 sessions — you load all of it every time.
  Context fills up. Slow. Expensive. Noisy.

  And every time the same question is asked — you call the LLM again.
  "What's the rate limit?" → LLM call. Same question 5 mins later → LLM call again.

WHAT YOU'LL BUILD:
  Step 1 — Extract facts + episodic memories after each turn → SQLite
  Step 2 — Extract understanding (patterns) after each turn → FAISS
  Step 3 — Semantic cache: check cache before LLM call, save after
  Step 4 — Load long-term memory at session start

THE CROSS-SESSION MOMENT:
  Session 1: Alex has a conversation. Facts + understanding extracted and saved.
  Session 2: New terminal. Agent says "Welcome back Alex. Last time you had
             a 401 caused by a trailing newline. Same issue today?"

RUN:
  source .venv/bin/activate                            ← activate first
  python modules/02-extraction/setup_db.py             ← run this first
  python modules/02-extraction/module.py
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
When you have context about the user from past conversations, use it naturally.
If you know their name, tier, SDK, or past issues — reference them.
Do not invent pricing, tier names, or specific limits you are not told about.
"""

EXTRACTION_PROMPT = """You are a memory extractor. Read this conversation turn and extract memories worth keeping.

Return a JSON object with this exact structure:
{{
  "facts": ["fact1", "fact2"],
  "episodic": ["event1", "event2"],
  "understanding": ["pattern1", "pattern2"]
}}

Definitions (extract from the conversation, do not copy these examples):
- facts: Simple, stable facts about the user. Example: "Alex uses Python SDK", "Alex is on free tier"
- episodic: Specific events with detail to recall later. Example: "Alex had 401 error caused by trailing newline in copy-pasted key"
- understanding: Patterns or tendencies across sessions. Example: "Alex makes copy-paste errors with credentials"

Rules:
- Only extract information ABOUT THE USER — their setup, errors they hit, things they did or discovered.
- Do NOT extract platform facts, rate limits, or general API knowledge.
- Do NOT extract what the agent said, suggested, or recommended.
- Do NOT extract statements like "user is still experiencing X" — only concrete resolutions or discoveries.
- Only extract understanding after a clear pattern, not a single incident.
- Empty lists are fine and often correct.
- Return valid JSON only. No explanation.

Conversation turn:
User: {user_message}
Agent: {agent_message}

Existing memories for context:
{existing_memories}
"""

# Suggested questions — same as Module 1 so students see extraction kick in
SUGGESTED_QUESTIONS = [
    "Hi, I'm getting a 401 Unauthorized error on all my API calls.",
    "I regenerated the key last week. It shows as active in the dashboard.",
    "Still getting 401. Any other ideas?",
    "Found it — there was a trailing newline when I copy-pasted the key.",
    "Fixed now. Thanks. I'm using the Python SDK by the way.",
    "What's the rate limit on the free tier?",
    "What's the rate limit on the free tier?",  # duplicate — hits cache on STEP 3
]


# ── Database setup ────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # Conversational turns (from Module 1)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session   TEXT NOT NULL,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Long-term memories — facts and episodic
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            type       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Semantic cache
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            question   TEXT NOT NULL,
            answer     TEXT NOT NULL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_turn(session: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO turns (session, role, content) VALUES (?, ?, ?)",
        (session, role, content)
    )
    conn.commit()
    conn.close()


def load_recent_turns(session: str, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM turns WHERE session = ? ORDER BY timestamp ASC LIMIT ?",
        (session, limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


def load_long_term_memories(user_id: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT type, content, timestamp FROM memories WHERE user_id = ? ORDER BY timestamp ASC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [{"type": r[0], "content": r[1], "timestamp": r[2]} for r in rows]


def save_memory(user_id: str, memory_type: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memories (user_id, type, content) VALUES (?, ?, ?)",
        (user_id, memory_type, content)
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Extract facts + episodic memories after each turn → SQLite
#
# Uncomment the function body below (remove the `pass` version above it).
# Re-run. After each turn you will see:
#   → saved fact: Alex uses Python SDK
#   → saved episodic: 401 fixed, trailing newline in copy-pasted key
# Query the DB: SELECT * FROM memories;
# ═══════════════════════════════════════════════════════════════════════════════

def extract_and_save(user_id: str, user_msg: str, agent_msg: str, existing: list):
    pass

# def extract_and_save(user_id: str, user_msg: str, agent_msg: str, existing: list):
#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
#     base_url = os.getenv("ANTHROPIC_BASE_URL")
#     client = anthropic.Anthropic(
#         api_key=api_key or "dummy",
#         auth_token=auth_token if not api_key else None,
#         base_url=base_url,
#     )
#     existing_text = "\n".join(f"[{m['type']}] {m['content']}" for m in existing) or "None yet"
#     prompt = EXTRACTION_PROMPT.format(
#         user_message=user_msg,
#         agent_message=agent_msg,
#         existing_memories=existing_text,
#     )
#     try:
#         response = client.messages.create(
#             model="claude-haiku-4-5-20251001",
#             max_tokens=300,
#             messages=[{"role": "user", "content": prompt}],
#         )
#         raw = response.content[0].text.strip()
#         if raw.startswith("```"):
#             raw = raw.split("```", 2)[1]
#             if raw.startswith("json"):
#                 raw = raw[4:]
#             raw = raw.strip()
#         extracted = json.loads(raw)
#     except Exception:
#         return []
#     saved = []
#     for f in extracted.get("facts", []):
#         save_memory(user_id, "fact", f)
#         saved.append(("fact", f))
#     for e in extracted.get("episodic", []):
#         save_memory(user_id, "episodic", e)
#         saved.append(("episodic", e))
#     for p in extracted.get("understanding", []):
#         save_understanding(p)
#         saved.append(("understanding", p))
#     return saved


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Extract understanding (patterns) → FAISS vector store
#
# Uncomment save_understanding + load_understanding below (remove the pass stubs).
# Re-run. After enough signal you will see:
#   → saved understanding: Alex makes copy-paste errors with credentials
# ═══════════════════════════════════════════════════════════════════════════════

def save_understanding(content: str):
    pass

# def save_understanding(content: str):
#     from langchain_community.vectorstores import FAISS
#     from langchain_huggingface import HuggingFaceEmbeddings
#     embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#     if os.path.exists(FAISS_PATH):
#         store = FAISS.load_local(FAISS_PATH, embedder, allow_dangerous_deserialization=True)
#         store.add_texts([content])
#     else:
#         store = FAISS.from_texts([content], embedder)
#     store.save_local(FAISS_PATH)


def load_understanding(query: str, k: int = 2) -> list:
    return []

# def load_understanding(query: str, k: int = 2) -> list:
#     from langchain_community.vectorstores import FAISS
#     from langchain_huggingface import HuggingFaceEmbeddings
#     if not os.path.exists(FAISS_PATH):
#         return []
#     embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#     store = FAISS.load_local(FAISS_PATH, embedder, allow_dangerous_deserialization=True)
#     docs = store.similarity_search(query, k=k)
#     return [doc.page_content for doc in docs]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Semantic cache: check before LLM call, save after
#
# Uncomment check_cache + save_to_cache below (remove the return None / pass stubs).
# Re-run. Ask question 6, then question 7 (identical). You will see:
#   Turn 6: LLM call → answer saved to cache
#   Turn 7: ⚡ Cache HIT — 0 tokens, 0ms LLM latency
# Query the DB: SELECT * FROM cache;
# ═══════════════════════════════════════════════════════════════════════════════

# def check_cache(user_id: str, question: str, threshold: float = 0.85):
#     cache_path = f"cache_faiss_{user_id}"
#     if not os.path.exists(cache_path):
#         return None
#     try:
#         from langchain_community.vectorstores import FAISS
#         from langchain_huggingface import HuggingFaceEmbeddings
#         embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#         store = FAISS.load_local(cache_path, embedder, allow_dangerous_deserialization=True)
#         results = store.similarity_search_with_score(question, k=1)
#         if results and results[0][1] < (1 - threshold):
#             cached_q = results[0][0].page_content
#             conn = sqlite3.connect(DB_PATH)
#             row = conn.execute(
#                 "SELECT answer FROM cache WHERE user_id=? AND question=? LIMIT 1",
#                 (user_id, cached_q)
#             ).fetchone()
#             conn.close()
#             return row[0] if row else None
#     except Exception:
#         return None

def check_cache(user_id: str, question: str, threshold: float = 0.85):
    return None


# def save_to_cache(user_id: str, question: str, answer: str):
#     conn = sqlite3.connect(DB_PATH)
#     conn.execute(
#         "INSERT INTO cache (user_id, question, answer) VALUES (?, ?, ?)",
#         (user_id, question, answer)
#     )
#     conn.commit()
#     conn.close()
#     cache_path = f"cache_faiss_{user_id}"
#     try:
#         from langchain_community.vectorstores import FAISS
#         from langchain_huggingface import HuggingFaceEmbeddings
#         embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#         if os.path.exists(cache_path):
#             store = FAISS.load_local(cache_path, embedder, allow_dangerous_deserialization=True)
#             store.add_texts([question])
#         else:
#             store = FAISS.from_texts([question], embedder)
#         store.save_local(cache_path)
#         return True
#     except Exception:
#         return True

def save_to_cache(user_id: str, question: str, answer: str):
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Load long-term memory at session start
#
# Find [STEP 4] in run() below and uncomment those lines.
# Quit, open a NEW terminal, re-run. You will see:
#   ✓ Loaded 2 long-term memories for alex-chen
#   [fact] Alex uses Python SDK
#   [episodic] 401 fixed, trailing newline in copy-pasted key
# The agent now has context before you say a word.
# ═══════════════════════════════════════════════════════════════════════════════


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


# ── Show memory tables ────────────────────────────────────────────────────────

def show_memory_tables():
    conn = sqlite3.connect(DB_PATH)

    memories = conn.execute(
        "SELECT type, content, timestamp FROM memories WHERE user_id=? ORDER BY timestamp ASC",
        (USER_ID,)
    ).fetchall()

    cache_rows = conn.execute(
        "SELECT question, answer FROM cache WHERE user_id=? ORDER BY timestamp ASC",
        (USER_ID,)
    ).fetchall()

    conn.close()

    if memories:
        tbl = Table(title="Long-term Memories (SQLite)", border_style="green")
        tbl.add_column("Type", width=12)
        tbl.add_column("Content", max_width=60)
        for mem_type, content, _ in memories:
            color = "cyan" if mem_type == "fact" else "yellow"
            tbl.add_row(f"[{color}]{mem_type}[/{color}]", content)
        console.print(tbl)
        console.print()

    if os.path.exists(FAISS_PATH):
        console.print(Panel(
            f"[magenta]FAISS index exists[/magenta] at ./{FAISS_PATH}/\n"
            "[dim]Contains understanding/patterns extracted from conversations[/dim]",
            border_style="magenta",
            title="Understanding Store",
        ))
        console.print()

    if cache_rows:
        tbl = Table(title="Semantic Cache (SQLite + FAISS)", border_style="blue")
        tbl.add_column("Question", max_width=40)
        tbl.add_column("Answer", max_width=40)
        for q, a in cache_rows:
            tbl.add_row(q[:50], a[:50] + "..." if len(a) > 50 else a)
        console.print(tbl)
        console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

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
    console.print(Rule("[bold]Module 2 — Long-term Memory Extraction + Semantic Cache[/bold]"))
    console.print()

    # ── [STEP 4] Load long-term memories at session start ─────────────────────
    # Remove the `long_term = []` line below to activate.
    # Then quit, open a NEW terminal, and re-run to see the cross-session moment.
    long_term = load_long_term_memories(USER_ID)
    understanding = load_understanding("user background and history")
    long_term = []  # ← STEP 4: delete this line

    # Build session context from long-term memories
    session_context = ""
    if long_term:
        facts = [m["content"] for m in long_term if m["type"] == "fact"]
        episodic = [m["content"] for m in long_term if m["type"] == "episodic"]
        if facts or episodic:
            session_context = "What I know about this user:\n"
            for f in facts:
                session_context += f"  [fact] {f}\n"
            for e in episodic:
                session_context += f"  [history] {e}\n"

    if long_term:
        console.print(Panel(
            f"[green]Loaded {len(long_term)} long-term memories for {USER_ID}[/green]\n\n"
            + "\n".join(f"  [{m['type']}] {m['content']}" for m in long_term),
            border_style="green",
            title="Long-term Memory Loaded",
        ))
        console.print()
    else:
        console.print(Panel(
            "[yellow]No long-term memories found for this user yet[/yellow]\n\n"
            "Run through the conversation — memories will be extracted after each turn.\n"
            "Then open a new terminal and run again to see the cross-session moment.\n\n"
            "[dim]Uncomment STEP 1 → STEP 2 → STEP 3 → STEP 4[/dim]",
            border_style="yellow",
            title="Current State",
        ))
        console.print()

    # Run the conversation
    console.print(Panel(
        "Suggested questions — copy-paste one at a time:\n\n"
        + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(SUGGESTED_QUESTIONS))
        + "\n\n[dim]Questions 6 and 7 are identical — watch for the cache hit on STEP 3.[/dim]\n"
        + "[dim]Type 'quit' to stop.[/dim]",
        border_style="dim",
        title="Try These",
    ))
    console.print()

    turn_num = 0
    while True:
        turn_num += 1
        console.print(Rule(f"[dim]Turn {turn_num}[/dim]", style="dim"))
        if turn_num == len(SUGGESTED_QUESTIONS) + 1:
            console.print("  [dim]Done — type 'quit', then open a new terminal and run again.[/dim]")
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

        # ── Check semantic cache first (Step 3) ────────────────────────────
        cached = check_cache(USER_ID, question)
        if cached:
            console.print(f"  [bold cyan]⚡ Cache HIT[/bold cyan] — 0 tokens, 0ms LLM latency")
            console.print(f"  [green]Agent:[/green] {textwrap.fill(cached, 70)}")
            console.print()
            continue

        # ── Build messages: session context + recent turns + question ──────
        messages = []

        if session_context:
            messages.append({
                "role": "user",
                "content": f"[Context about this user]\n{session_context}"
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I have context about this user."
            })

        recent = load_recent_turns(SESSION_ID)
        messages += recent
        messages.append({"role": "user", "content": question})

        # ── Call agent ─────────────────────────────────────────────────────
        with console.status("[dim]thinking...[/dim]", spinner="dots"):
            answer = call_agent(messages)

        console.print(f"  [green]Agent:[/green] {textwrap.fill(answer, 70)}")
        console.print()

        # ── Save turn ──────────────────────────────────────────────────────
        save_turn(SESSION_ID, "user", question)
        save_turn(SESSION_ID, "assistant", answer)

        # ── Save to cache (Step 3) ─────────────────────────────────────────
        cache_saved = save_to_cache(USER_ID, question, answer)
        if cache_saved:
            console.print(f"  [dim]→ inserted into [bold]cache[/bold]: Q: {question[:50]}{'...' if len(question)>50 else ''}[/dim]")
            console.print(f"  [dim]                              A: {answer[:50]}{'...' if len(answer)>50 else ''}[/dim]")
            console.print()

        # ── Extract and save memories (Steps 1 + 2) ────────────────────────
        existing = load_long_term_memories(USER_ID)
        with console.status("[dim]extracting memories...[/dim]", spinner="dots"):
            saved_memories = extract_and_save(USER_ID, question, answer, existing)
        if saved_memories:
            for label, content in saved_memories:
                console.print(f"  [dim]→ saved {label}: {content}[/dim]")
        else:
            console.print(f"  [dim]→ no memories extracted this turn[/dim]")
        console.print()
        console.print(Rule(style="dim"))

    # ── Show what got saved ────────────────────────────────────────────────
    console.print(Rule("[dim]Memory State After This Session[/dim]", style="dim"))
    console.print()
    show_memory_tables()

    console.print(Rule("[bold]End of Module 2[/bold]"))
    console.print()

    if long_term:
        console.print(Panel(
            "[bold green]✓ Cross-session memory working[/bold green]\n\n"
            "The agent remembered Alex from a previous session.\n"
            "Facts and episodic memories loaded from SQLite.\n"
            "Understanding loaded from FAISS.\n\n"
            "[dim]Next → Module 3: Memory Manager routing[/dim]",
            border_style="green",
            title="Module 2 Complete",
        ))
    else:
        console.print(Panel(
            "Session complete — memories extracted and saved.\n\n"
            "Now open a NEW terminal and run again:\n"
            "  python modules/02-extraction/module.py\n\n"
            "Long-term memories will load at the start of the next session.\n\n"
            "[dim]Then run Module 3 to see the Memory Manager route those memories.[/dim]",
            border_style="blue",
            title="Next Step",
        ))
    console.print()


if __name__ == "__main__":
    run()
