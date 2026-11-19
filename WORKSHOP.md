# Memory Management for AI Agents
### A 2.5-hour hands-on workshop

> Build a memory-aware AI agent that remembers conversations, knows its product, and recalls past interactions — using Claude, SQLite, and FAISS.

---

## Schedule

| Time | Block | Format |
|------|-------|--------|
| 0:00–0:15 | Setup & welcome | Setup |
| 0:15–0:45 | Part 1 — Why agents need memory | Talk + demo |
| 0:45–1:05 | Module 1 — Conversational memory | Hands-on |
| 1:05–1:20 | ☕ Break | — |
| 1:20–1:35 | Part 2 — Semantic & Episodic memory | Talk |
| 1:35–1:55 | Module 2 — Semantic memory | Hands-on |
| 1:55–2:15 | Module 3 — Memory Manager | Hands-on |
| 2:15–2:30 | Production issues + Q&A | Talk + Q&A |

---

## Part 1 — Why Agents Need Memory

### 1.1 The LLM Context Window

Every LLM has a **context window** — the maximum amount of text it can read at one time.
Think of it as the LLM's **RAM**.

```
┌─────────────────────────────────────────────────────┐
│              LLM Context Window                     │
│                                (e.g. 200k tokens)   │
│                                                     │
│  ┌─────────────────────────┐                        │
│  │  System prompt          │  ░░░░░░░░░░░░░░░░░░░  │
│  ├─────────────────────────┤                        │
│  │  Conversation history   │  ████████░░░░░░░░░░░  │
│  ├─────────────────────────┤                        │
│  │  Retrieved documents    │  ████░░░░░░░░░░░░░░░  │
│  ├─────────────────────────┤                        │
│  │  Current question       │  █░░░░░░░░░░░░░░░░░░  │
│  └─────────────────────────┘                        │
│                                                     │
│  When full → oldest messages get DROPPED            │
└─────────────────────────────────────────────────────┘
```

**The problem:** conversations keep growing, but the context window is fixed.
Once it fills up, the agent starts forgetting the beginning of the conversation.

This is not a bug. It is a fundamental constraint of how LLMs work.

> **Key insight:** The context window is the LLM's working memory — fast, powerful, but limited and temporary.
> Everything outside the context window is **invisible** to the agent.

---

### 1.2 Stateless Agent — What Failure Looks Like

An agent with no external memory is called a **stateless agent**.
It can perceive input, reason, and respond — but it forgets everything after each turn.

Here is what a stateless agent looks like in a real support scenario:

```
┌─────────────────────────────────────────────────────────────────┐
│                   STATELESS AGENT (no memory)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Turn 1   User:  "I'm getting a 401 error on my API calls."     │
│           Agent: "A 401 means your API key is invalid.          │
│                   Can you check your Authorization header?"     │
│                                                                 │
│  Turn 2   User:  "I checked — the key looks right."             │
│           Agent: "Try regenerating the key in the dashboard."   │
│                                                                 │
│  Turn 3   User:  "Still broken. Same error."                    │
│           Agent: "What error are you seeing?"  ← FORGOT         │
│                                                                 │
│  Turn 4   User:  "Same issue as last week too."                 │
│           Agent: "I don't have any record of previous           │
│                   interactions. Can you describe the issue?"    │
│                              ↑ FORGOT LAST WEEK TOO             │
└─────────────────────────────────────────────────────────────────┘
```

**Three things broke:**
1. The agent forgot the conversation **within the same session** (Turn 3)
2. The agent has no memory of **past sessions** (Turn 4)
3. The agent doesn't know the product — it gave a generic answer

**This is the problem we are solving today.**

---

### 1.3 Memory-Augmented Agent — The Fix

A memory-augmented agent stores information in an **external database** — outside the context window.
Before each response, it **retrieves** what it needs and loads it into the context window.

```
┌──────────────────────────────────────────────────────────────────┐
│                 MEMORY-AUGMENTED AGENT                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User query                                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐    reads from    ┌──────────────────────────┐  │
│  │             │ ◄─────────────── │   External Memory        │  │
│  │    Agent    │                  │                          │  │
│  │  (Claude)   │ ─────────────►  │  • Conversation history  │  │
│  │             │    writes to     │  • Product knowledge     │  │
│  └─────────────┘                  │  • Past tickets          │  │
│       │                           └──────────────────────────┘  │
│       ▼                                                          │
│   Response (grounded, contextual, remembers history)            │
└──────────────────────────────────────────────────────────────────┘
```

Same conversation, now with memory:

```
  Turn 3   User:  "Still broken. Same error."
           Agent: "Still seeing the 401 from your API key?         ← remembered Turn 1
                   Let me check if this happened before..."        ← checks past tickets
                   "I see you had a similar issue on Oct 14 —
                   you hadn't updated the key in production.
                   Is that the case again?"                        ← recalled past ticket
```

---

### 1.4 The Six Memory Types

Not all memory is the same. Just like humans have different kinds of memory, agents do too.

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT MEMORY TYPES                          │
├────────────────────────┬────────────────────────────────────────┤
│    SHORT-TERM          │    LONG-TERM                           │
├────────────────────────┼────────────────────────────────────────┤
│                        │                                        │
│  Working Memory        │  Semantic Memory                       │
│  The LLM context       │  Facts & knowledge base                │
│  window itself.        │  "Free tier = 1k req/day"              │
│  Fast, temporary.      │  Stored in a vector store.             │
│                        │                                        │
│  Conversational        │  Episodic Memory                       │
│  Memory                │  Past events & interactions            │
│  Current session       │  "User had 401 issue Oct 14"           │
│  chat history.         │  Stored with timestamps.               │
│  Stored in SQL.        │                                        │
│                        │  Procedural Memory                     │
│                        │  Learned workflows & patterns          │
│                        │  "Always check env vars for 401"       │
│                        │                                        │
│                        │  Summary Memory                        │
│                        │  Compressed old conversations          │
│                        │  When context window fills up.         │
└────────────────────────┴────────────────────────────────────────┘
```

> **Today we build three:** Conversational, Semantic, and Episodic.
> The Memory Manager ties them all together.

---

### 1.5 The Memory Manager

The **Memory Manager** is the brain between the agent and the database.
It decides: which memory to read, what to write, and when to forget.

```
┌─────────────────────────────────────────────────────────────────┐
│                      MEMORY MANAGER                             │
│                                                                 │
│    Agent asks a question                                        │
│           │                                                     │
│           ▼                                                     │
│    ┌─────────────────────────────────────────────────────┐     │
│    │  Route: what memory does this question need?        │     │
│    │                                                     │     │
│    │  "My API key isn't working"                         │     │
│    │       → read conversational (what did we say?)      │     │
│    │       → read semantic (what do docs say about 401?) │     │
│    │       → read episodic (did this happen before?)     │     │
│    └─────────────────────────────────────────────────────┘     │
│           │                                                     │
│           ▼                                                     │
│    Retrieved context injected into context window               │
│           │                                                     │
│           ▼                                                     │
│    Agent responds — then Memory Manager writes back             │
│       → save this turn to conversational memory                 │
│       → save any new facts learned                              │
└─────────────────────────────────────────────────────────────────┘
```

**Two types of memory operations:**

| Type | Description | Example |
|------|-------------|---------|
| **Deterministic** | Always runs, regardless of query | Save every conversation turn |
| **Agent-triggered** | Agent decides when to call it | "Summarize this thread" |

---

### 1.6 Memory in Code — From Variable to Database

Before we build, let's see what memory looks like at each level:

**Level 1 — A Python variable (no persistence)**
```python
memory = []
memory.append({"role": "user", "content": "I have a 401 error"})
# Gone when the process ends
```

**Level 2 — SQLite (persistent, exact lookup)**
```python
# Store conversation turns → retrieve by session ID
# Survives restarts. Fast for exact queries.
# Used for: conversational memory
```

**Level 3 — FAISS vector store (persistent, semantic search)**
```python
# Store document embeddings → retrieve by meaning
# "rate limit" matches "429 error" even without exact words
# Used for: semantic memory (knowledge base)
```

> **The Memory Core** is the database. All three levels feed into it.
> The Memory Manager is the code that reads and writes to it.

---

## Module 1 — Conversational Memory

**What:** Store each conversation turn in SQLite. Reload it at the start of each turn.

**Without it:** The agent forgets what was said two messages ago.

**With it:** The agent holds context for the entire session.

```
Run: python modules/01-conversational/module.py
```

Uncomment one step at a time and re-run after each one.

---

## Module 2 — Semantic Memory

**What:** Embed the product knowledge base into FAISS. Retrieve relevant docs per query.

**Without it:** The agent gives generic answers ("please check the docs").

**With it:** The agent answers from actual product knowledge ("free tier is 1k req/day, upgrade to Pro for 100k").

```
Run: python modules/02-semantic/module.py
```

---

## Module 3 — Memory Manager

**What:** Build the routing logic that decides which memory to read and write per query.

**Without it:** Each memory type is an isolated bucket — the agent uses them all blindly.

**With it:** The right memory is retrieved for the right question. Past tickets surface when relevant. New learnings get written back.

```
Run: python modules/03-memory-manager/module.py
```

---

## Part 2 — Production Issues

### Context window fills up — summarize

When the conversation grows too long, compress it:

```
Long conversation (500 turns)
        │
        ▼
  summarize_and_store()
        │
        ▼
  [Summary ID: abc123] "User resolved 401 issue, upgraded to Pro"
        │
        ▼
  expand_summary("abc123")  ← agent calls this only when it needs detail
```

### Memory bloat — when to forget

Not everything deserves to be stored forever:
- **Keep:** resolved issues, user preferences, account changes
- **Forget:** casual greetings, duplicate questions, temporary errors

### Stale memory — timestamps matter

A "free tier = 1k req/day" fact written 6 months ago might be wrong today.
Always store timestamps. Build expiry policies for facts that change.

---

## Q&A

Common questions:

**Q: How is this different from just passing the full conversation history?**
> Full history fills the context window. Memory retrieval passes only what's relevant — higher signal, lower token cost.

**Q: When should memory operations be deterministic vs agent-triggered?**
> Deterministic for reliability (always save turns, always load recent history).
> Agent-triggered for quality (summarize only when the agent judges it's needed).

**Q: What's the right database for production?**
> SQLite works up to millions of rows. For scale: Postgres + pgvector, or a dedicated vector DB like Pinecone or Weaviate.
