# Memory Management for AI Agents
### A 2.5-hour hands-on workshop — Facilitator Guide

> Build a memory-aware AI agent that remembers conversations, learns facts, recalls past events, and understands user patterns — using Claude, SQLite, and FAISS.

**Date:** Nov 21, 2024 · 11 AM – 1:30 PM PT · Online

---

## Schedule

| Time | Block | Format |
|------|-------|--------|
| 0:00–0:15 | Setup & welcome | Setup |
| 0:15–0:40 | Part 1 — Why agents need memory | Talk + Q&A |
| 0:40–0:55 | Demo — Context window crash + recovery | Demo |
| 0:55–1:15 | Module 1 — Conversational memory | Hands-on |
| 1:15–1:25 | ☕ Break | — |
| 1:25–1:45 | Module 2 — Long-term memory extraction + semantic cache | Hands-on |
| 1:45–2:05 | Module 3 — Memory Manager routing | Hands-on |
| 2:05–2:20 | Demo 2 — Mem0 (industry standard) | Demo |
| 2:20–2:30 | Q&A + wrap up | Q&A |

---

## Setup (0:00–0:15)

While students run `python check_setup.py`:

> **Before running:** students need a `.env` file with their API key.
> Tell them:
> ```
> cp .env.example .env
> # then open .env and paste their ANTHROPIC_API_KEY
> ```
> **Getting an Anthropic API key:**
> 1. Go directly to [platform.claude.com/settings/keys](https://platform.claude.com/settings/keys)
> 2. Sign up or log in
> 3. Click **Create Key** — copy it immediately (shown only once)
> 4. Save it somewhere safe (password manager, notes) — never share it, never commit it to git
> 5. Paste it into `.env` as `ANTHROPIC_API_KEY=sk-ant-...`
>
> Free tier works for this workshop. No credit card required to start.

- Ask: "Who here has built something with an LLM?"
- Ask: "Who ran into a problem where the agent forgot something?"

That's the problem we're solving today.

---

## Part 1 — Why Agents Need Memory (0:15–0:40)

### 1.1 LLMs are stateless

Every API call is completely fresh. Claude does not remember the previous call.

```
Call 1:   You type: "I am getting a 401 error while calling the GitHub API"
          messages = [{"role": "user", "content": "I am getting a 401 error while calling the GitHub API"}]
          → Claude responds

Call 2:   You type: "Still broken"
          messages = [{"role": "user", "content": "Still broken"}]
          → Claude has NO idea what "still broken" means
            It never saw Call 1
```

If you want the agent to remember — **your code must pass the history.**
The LLM does not manage this for you.

**Try it now:**
```
python demo/stateless.py
```
You type two messages. The second should only make sense if Claude remembered the first ("Still broken", "Same error", "What about that?"). Watch it ask you to start over — it never saw Call 1.

> **Audience question:**
> "Who here has built a chatbot that just passes the full conversation history every turn?
>  What happened when the conversation got long?"

---

### 1.2 What is the context window?

Every time you call the Claude API, you pass a `messages` list. The context window is the maximum size of that list — measured in **tokens** (roughly 1 token ≈ 1 word).

```
client.messages.create(
    model="claude-haiku-4-5-20251001",
    messages=[...],   ← everything here counts toward the limit
)
```

**Everything counts toward the limit:**
- System prompt
- Conversation history (every turn so far)
- Tool outputs
- Retrieved documents

Claude Haiku has a **200,000 token** context window (~150,000 words). Sounds huge — but in a long-running agent with many turns, it fills faster than you expect.

**What happens when it overflows:**
```
anthropic.BadRequestError: prompt is too long:
200011 tokens > 200000 maximum
```

The API throws an error. Your agent crashes. The user loses the conversation.

That's what `demo/context_window.py` shows — we'll run it right after this section. And that's why we need memory — to decide what stays in the window and what gets stored elsewhere.

> **Audience question:**
> "If the context window is 200,000 tokens — why can't we just always pass everything?"
>
> Expected: cost (every token costs money), latency (bigger prompt = slower response), and noise (more irrelevant context = worse answers)

---

### 1.3 Short-term vs Long-term — with examples

![Forms of Agent Memory](assets/forms_of_agent_memory.png)

**Short-term memory — exists only while the task is running:**

| Type | Example |
|------|---------|
| Working memory | Agent's scratchpad during task execution — plans, tool outputs, intermediate steps. Discarded when the task completes, even if the terminal is still open |
| Semantic cache | You asked "what's the rate limit?" — agent cached the answer. Ask again: instant reply, no LLM call |

> **Key design principle:**
> Working memory should NOT be the entire conversation history. It should be a curated, task-specific state the agent updates as execution progresses.
>
> Design memory around two questions:
> 1. What should the agent remember about the user and previous interactions? → **Long-term memory**
> 2. What does the agent need to remember to finish the current task? → **Working memory**

**Long-term memory — survives after the terminal closes:**

| Type | Example |
|------|---------|
| Conversational memory | "Alex told me last week they use Python SDK" — retrieved when relevant to a new session |
| Facts | "Alex is on the free plan" — remembered next session, next week |
| Episodic | "Nov 19 — Alex had a 401 caused by a trailing newline in their key" |
| Understanding | "Alex always makes copy-paste errors with credentials" — pattern learned over many sessions |

**The two-terminal test:**
- Close the terminal → short-term is gone
- Open a new terminal → long-term is still there

> **Audience question:**
> "If you close your laptop and reopen it tomorrow — what should the agent remember about you?
>  What should it forget?"

---

### 1.4 Facts vs Understanding — the most important distinction

From Google's agent memory architecture:

**Facts are exact. You look them up.**
```
"What plan is my DevCore account on?"  →  SQL query  →  "Pro"
"What did Alex buy?"     →  SQL query  →  exact rows
```

**Understanding is meaning. You recall it.**
```
"What do I know about Alex's style?"  →  vector search  →  "prefers simple, dark colors"
"What patterns does Alex have?"       →  vector search  →  "makes copy-paste errors"
```

> **Common mistake:** putting everything in the vector store.
> Vector stores return *similar* results, not *exact* results.
> If Alex asks "what tier am I on?" — the agent should not *guess from similar memories*.
> It should query the database for the exact row.

---

### 1.5 How memory is written — sync vs async

**Facts → write immediately (synchronous)**
```
User: "I just upgraded to Pro"
         ↓
Agent writes immediately: { fact: "Alex on Pro tier", timestamp: now }
         ↓
If the user asks next turn: "What plan is my DevCore account on?" → answer is there
```

**Understanding → write after enough context (asynchronous)**
```
Turn 3: User fixes 401 — trailing newline again
Turn 7: User fixes 403 — copy-pasted scope name wrong
Turn 12: User fixes 401 — trailing newline again
         ↓
Pattern emerges: "Alex makes copy-paste errors with credentials"
         ↓
Extract AFTER session, not during — don't update identity from one sentence
```

> **Audience question:**
> "Why is it dangerous to update understanding from a single sentence?
>  Example: user says 'maybe I like yellow today' — should the agent remember 'user likes yellow'?"

---

## Demo — Context Window Crash + Recovery (0:40–0:55)

```
python demo/context_window.py
```

**What to say while running:**

"This is working memory — the context window. Watch the bar fill up as we talk.
At 75% — yellow warning. At 90% — the API throws a real error.
This is not simulated. This is what your users hit in production.

Watch what happens next — the Memory Manager kicks in.
It compresses the old turns into a summary.
Context drops. Conversation continues.
The agent didn't lose the thread — it summarized it."

**After the demo:**
> "This is summary memory — the 6th type. Compression of old conversations.
>  The agent didn't forget — it remembered the shape, not every word."

---

## Module 1 — Conversational Memory (0:55–1:15)

### Theory (3 mins)

"You just saw the context window fill up. That's working memory — the context window itself.

Now we're going to build conversational memory — the turns of this session stored in SQLite.

Without it: agent forgets mid-conversation.
With it: agent holds full context for the session.

And here's the key — because it's on disk, it survives the terminal closing.
That's the bridge between short-term and long-term."

### The two-terminal moment

**Before adding memory:**
```
Terminal 1:
  You: I have a 401 error
  You: Same issue as last week
  Agent: I don't have any record of previous interactions  ← fails

[Close terminal. Open new terminal.]

Terminal 2:
  You: What was my issue last time?
  Agent: I have no context from previous sessions  ← blank slate
```

**After adding memory:**
```
Terminal 1:
  You: I have a 401 error
  You: Fixed it — trailing newline
  [Memory saved to SQLite]

[Close terminal. Open new terminal.]

Terminal 2:
  You: What was my issue last time?
  Agent: Last session you had a 401 error caused by a trailing newline
         in your API key  ← remembers
```

### Build

```
python modules/01-conversational/module.py
```

Uncomment STEP 1 → STEP 2 → STEP 3

**STEP 1:** Create SQLite `turns` table
**STEP 2:** Save every turn (sync — write immediately)
**STEP 3:** Load history before each call

### After Module 1

> **Audience question:**
> "You're now saving every turn. What happens after 1000 turns?
>  You load all of them every time — what's wrong with that?"
>
> Expected: context fills up, slow, expensive
> → That's what Module 2 solves

---

## Module 2 — Long-term Memory Extraction + Semantic Cache (1:25–1:45)

### Theory (3 mins)

"Module 1 saves every word. That's not how humans remember.

A support agent doesn't remember every word of a call.
They remember: 'Alex called Nov 15, had a 401, trailing newline, fixed.'
That's episodic memory — a specific event, compressed, with a timestamp.

They also know: 'Alex always makes copy-paste errors.'
That's understanding — a pattern across many sessions.

We're going to build both. Claude reads the conversation and extracts what matters.

And one more thing — semantic cache. If the same question gets asked twice,
why call the LLM again? Cache the answer. Retrieve it by meaning, not exact match."

### Semantic cache — the cost saver

```
Turn 6: "What's the rate limit on the free tier?"
        → no cache hit → LLM call → "100 req/min"
        → SAVE TO CACHE: { question, answer, embedding }

Turn 7: "What's the rate limit on the free tier?"  ← same question
        → semantic search on cache
        → HIT — identical question
        → return cached answer instantly
        → ⚡ 0 tokens used, 0ms LLM latency
```

Students see in terminal:
```
  Agent: Free tier is 100 requests per minute.

  ⚡ Cache HIT — 0 tokens, 0ms LLM latency
  Agent: Free tier is 100 requests per minute.
```

**Where cache is stored:**
- SQLite → the Q&A pair (question text + answer text)
- FAISS → the question embedding (for semantic similarity search)

### What gets extracted

```
Conversation turn:
  User: "Fixed it — was a trailing newline in the key I copy-pasted"
  Agent: "Great, that's a common issue. Always check for whitespace."
          ↓
Claude Haiku extracts:
  Fact:      "Alex uses copy-paste for API keys"        → SQLite (sync)
  Episodic:  "401 fixed, trailing newline in copy-pasted key"  → SQLite (sync)
  Understanding: "Alex makes copy-paste errors"        → FAISS (async)
```

### The cross-session moment

```
─── Session 1 (run the script) ──────────────────────
  You: Hi I'm getting a 401 error
  You: Fixed it, was a trailing newline
  [Memory extracted and saved]
  ✓ Fact: "Alex had 401 — trailing newline"
  ✓ Understanding: "Alex makes copy-paste errors"

[Close terminal]

─── Session 2 (run the script again) ────────────────
  [Long-term memory loads at session start]
  Agent greets fresh — but now has context if Alex mentions past issues
```

### Build

```
python modules/02-extraction/module.py
```

Uncomment STEP 1 → STEP 2 → STEP 3 → STEP 4

**STEP 1:** Extract facts + episodic after each turn → save to SQLite
**STEP 2:** Extract understanding after each turn → save to FAISS
**STEP 3:** Add semantic cache — check cache before LLM call, save after
**STEP 4:** Load long-term memory at session start

### After Module 2

> **Audience question:**
> "Claude just extracted memories from the conversation.
>  What could go wrong?
>  Should users be able to delete their memories?"
>
> Expected: wrong extraction, stale facts, privacy/GDPR

---

## Module 3 — Memory Manager Routing (1:45–2:05)

### Theory (3 mins)

"You now have three memory stores:
  - SQLite for conversational turns
  - SQLite for facts and episodic memories
  - FAISS for understanding

Every query hits all three? That's slow and noisy.
The right answer for 'what tier am I on?' does not need FAISS.
The right answer for 'what do I usually do wrong?' does not need an exact SQL lookup.

The Memory Manager decides what to read and what to write for each query."

### The routing logic

```
Query: "What plan is my DevCore account on?"
  → exact fact → SQL query → "Pro tier"

Query: "Same issue as last week"
  → episodic → SQL query by timestamp → "Nov 15 — 401, trailing newline"

Query: "What do I usually get wrong?"
  → understanding → FAISS semantic search → "copy-paste errors with credentials"

Query: "How do I fix a 429 error?"
  → no personal memory needed → agent answers from training
```

### Build

```
python modules/03-memory-manager/module.py
```

Uncomment STEP 1 → STEP 2 → STEP 3

**STEP 1:** Route reads — which store for which query type
**STEP 2:** Route writes — sync facts, async understanding
**STEP 3:** Full loop — read → respond → write → next turn

### After Module 3

> **Audience question:**
> "When should memory be deleted?
>  What's dangerous about keeping everything forever?"
>
> Expected: stale facts, wrong answers, privacy, storage cost

---

## Demo 2 — Mem0 (2:05–2:20)

```
python demo/mem0_demo.py
```

"You just built this from scratch — SQLite, FAISS, extraction, routing.
69,000 GitHub stars. This is the industry standard for agent memory.

Watch how many lines this takes with Mem0."

```python
from mem0 import Memory

memory = Memory.from_config(config)  # config: Claude Haiku + FAISS (no Docker needed)

# After each turn — Mem0 handles extraction, storage, dedup
memory.add(messages, user_id="alex-chen")

# Next session — Mem0 handles routing, retrieval, ranking
results = memory.search("401 error", user_id="alex-chen", limit=3)
```

"Same architecture you built. Facts in SQL. Understanding in vectors.
Extraction by LLM. Retrieval with semantic search + reranking.
Now you understand what's happening inside."

---

## Q&A (2:20–2:30)

**Q: How is this different from just passing full conversation history?**
> Full history fills the context window. Memory retrieval passes only what's relevant — higher signal, lower token cost.

**Q: When should memory operations be synchronous vs asynchronous?**
> Sync for facts — user expects them saved immediately.
> Async for understanding — needs enough context, don't update identity from one sentence.

**Q: What database should I use in production?**
> SQLite works up to millions of rows. For scale: Postgres + pgvector, or Pinecone/Weaviate for vectors.

**Q: How does the Memory Manager know what type of query it is?**
> Keyword matching works for demos. In production: small LLM classifier per query. Adds ~50ms but far more accurate.

**Q: Should users be able to delete their memories?**
> Yes — GDPR requires it. Build a `delete_memories(user_id)` function from day one.

**Q: What happens when extracted memory is wrong?**
> This is real. Use confidence scores. Flag low-confidence extractions for review. Don't auto-write everything.

---

## Key Takeaways

1. **LLMs are stateless** — your code manages memory, not the LLM
2. **Facts vs Understanding** — exact lookup vs semantic recall, different stores
3. **Sync vs Async writes** — facts immediately, understanding after enough context
4. **Two-terminal test** — if it survives a terminal close, it's long-term memory
5. **Extraction compresses** — you store what matters, not every word
6. **Memory Manager routes** — right store for right query, every time
