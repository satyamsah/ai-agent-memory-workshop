# Memory Management for AI Agents

A hands-on workshop. Build a memory-aware support agent from scratch using Claude, SQLite, and FAISS.

**Workshop:** Nov 21, 2024 · 11 AM – 1:30 PM PT · Online

---

## What you'll build

A DevCore API support agent that:
- Remembers everything said in a conversation (conversational memory)
- Extracts and stores facts, episodic events, and patterns from conversations (long-term memory)
- Caches repeated questions so they don't require an LLM call (semantic cache)
- Routes each query to the right memory source (Memory Manager)
- Uses Mem0 — the industry-standard memory library — to do all of that in 2 lines

---

## Setup (do this before the workshop)

**1. Clone the repo**
```bash
git clone https://github.com/satyamsah/ai-agent-memory-workshop
cd ai-agent-memory-workshop/memory-workshop
```

**2. Create a virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set your API key**
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key:
# ANTHROPIC_API_KEY=sk-ant-...
```
Get your key at [console.anthropic.com](https://console.anthropic.com).

**5. Run the setup check**
```bash
python check_setup.py
```

All checks should pass before the workshop starts.

---

## Workshop structure

| File | What it is |
|------|-----------|
| `demo/context_window.py` | Demo — context window fills up and crashes, Memory Manager rescues it |
| `demo/mem0_demo.py` | Final demo — Mem0 (69k GitHub stars) does the same thing in 2 lines |
| `modules/01-conversational/module.py` | Module 1 — SQLite conversational memory + two-terminal test |
| `modules/02-extraction/module.py` | Module 2 — LLM extraction → facts/episodic (SQLite) + understanding (FAISS) + semantic cache |
| `modules/03-memory-manager/module.py` | Module 3 — Memory Manager routing (right store for right query) |
| `check_setup.py` | Environment validator |
| `WORKSHOP.md` | Facilitator guide with schedule, theory, and Q&A questions |

---

## Running the demo

```bash
python demo/context_window.py
```

Watch a real conversation with Claude fill up an artificial 1,200-token context window.
At 90% full — the API throws a real error. Then the Memory Manager rescues it.

---

## Running the modules

Each module follows the same pattern:
1. Run as-is — the agent is stateless (no memory)
2. Uncomment one STEP at a time
3. Re-run after each step — watch the agent gain memory
4. After all steps: close the terminal, open a new one, run again — it remembers

```bash
python modules/01-conversational/module.py
python modules/02-extraction/module.py
python modules/03-memory-manager/module.py
```

---

## Final demo — Mem0

```bash
python demo/mem0_demo.py
```

After building everything from scratch, watch Mem0 do the same thing with 2 API calls.
You'll understand exactly what's happening inside because you just built it.

---

## Stack

- **LLM:** Claude Haiku (`claude-haiku-4-5-20251001`)
- **Conversational memory:** SQLite
- **Facts + episodic:** SQLite
- **Understanding + semantic cache:** FAISS + sentence-transformers (`all-MiniLM-L6-v2`)
- **Industry standard:** Mem0 (`mem0ai`)
- **Terminal UI:** Rich

