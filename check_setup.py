"""
check_setup.py — Verify your environment before the workshop starts.

Run:  python check_setup.py
"""

import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

console = Console()

checks = []


def ok(label, detail=""):
    checks.append(("✓", "green", label, detail))


def fail(label, detail=""):
    checks.append(("✗", "red", label, detail))


def warn(label, detail=""):
    checks.append(("?", "yellow", label, detail))


console.print()
console.print(Rule("[bold]Setup Check — Memory Management Workshop[/bold]"))
console.print()

# ── Python version ────────────────────────────────────────────────────────────
major, minor = sys.version_info[:2]
if major == 3 and minor >= 9:
    ok("Python version", f"{major}.{minor}")
else:
    fail("Python version", f"Found {major}.{minor} — need 3.9+")

# ── Packages ──────────────────────────────────────────────────────────────────
packages = {
    "anthropic": "anthropic",
    "rich": "rich",
    "dotenv": "python-dotenv",
    "langchain_community": "langchain-community",
    "langchain_huggingface": "langchain-huggingface",
    "faiss": "faiss-cpu",
    "sentence_transformers": "sentence-transformers",
    "numpy": "numpy",
    "mem0": "mem0ai",
    "sqlite3": "(built-in)",
}

for module_name, pkg_name in packages.items():
    try:
        __import__(module_name)
        ok(f"Package: {pkg_name}")
    except ImportError:
        if pkg_name == "(built-in)":
            fail(f"Package: {module_name} (built-in missing)")
        else:
            fail(f"Package: {pkg_name}", f"pip install {pkg_name}")

# ── Credentials ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
base_url = os.getenv("ANTHROPIC_BASE_URL")

if api_key:
    ok("ANTHROPIC_API_KEY", f"...{api_key[-4:]}")
elif auth_token:
    ok("ANTHROPIC_AUTH_TOKEN", "(company proxy)")
    if base_url:
        ok("ANTHROPIC_BASE_URL", base_url)
    else:
        warn("ANTHROPIC_BASE_URL", "not set — required with AUTH_TOKEN")
else:
    fail("API credentials", "Set ANTHROPIC_API_KEY in .env")

# ── Live API test ─────────────────────────────────────────────────────────────
if api_key or auth_token:
    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(
            api_key=api_key or "dummy",
            auth_token=auth_token if not api_key else None,
            base_url=base_url,
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say: OK"}],
        )
        ok("Claude API call", resp.content[0].text.strip())
    except Exception as e:
        fail("Claude API call", str(e)[:80])

# ── Embedding model (downloads ~90MB on first run) ────────────────────────────
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    with console.status("[dim]Loading embedding model (may download on first run)...[/dim]"):
        emb = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        result = emb.embed_query("test")
    ok("Embedding model", f"all-MiniLM-L6-v2 — {len(result)}d vector")
except Exception as e:
    fail("Embedding model", str(e)[:80])

# ── FAISS smoke test ──────────────────────────────────────────────────────────
try:
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    emb = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    store = FAISS.from_texts(["DevCore rate limit is 10 req/sec on free tier"], emb)
    docs = store.similarity_search("rate limit", k=1)
    ok("FAISS vector store", f"indexed 1 doc, retrieved: '{docs[0].page_content[:40]}...'")
except Exception as e:
    fail("FAISS vector store", str(e)[:80])

# ── Results ───────────────────────────────────────────────────────────────────
console.print()
tbl = Table(show_header=False, box=None, padding=(0, 1))
tbl.add_column("", width=3)
tbl.add_column("", min_width=35)
tbl.add_column("", style="dim")

for symbol, color, label, detail in checks:
    tbl.add_row(f"[{color}]{symbol}[/{color}]", label, detail)

console.print(tbl)
console.print()

failures = [c for c in checks if c[0] == "✗"]
warnings = [c for c in checks if c[0] == "?"]

if not failures:
    console.print(Panel(
        "[bold green]All checks passed — you're ready for the workshop![/bold green]\n\n"
        "Start with the demo:\n"
        "  [bold]python demo/context_window.py[/bold]\n\n"
        "Then the modules in order:\n"
        "  [bold]python modules/01-conversational/module.py[/bold]\n"
        "  [bold]python modules/02-extraction/module.py[/bold]\n"
        "  [bold]python modules/03-memory-manager/module.py[/bold]\n\n"
        "Final demo:\n"
        "  [bold]python demo/mem0_demo.py[/bold]",
        border_style="green",
        title="Ready",
    ))
else:
    console.print(Panel(
        f"[bold red]{len(failures)} check(s) failed.[/bold red]\n\n"
        "Fix the issues above, then re-run:\n"
        "  [bold]python check_setup.py[/bold]",
        border_style="red",
        title="Action Required",
    ))

console.print()
