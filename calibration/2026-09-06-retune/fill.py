"""Finish the variant-C scoring run that OpenRouter's free-tier daily limit cut short.

Idempotent: scores only the entries still null in scores-c.json and writes them
back, so it can be run as many times as the quota allows. `rubric-c.md` here is
the version that shipped to rubric.md on 2026-09-06 — it is kept separately so a
later edit to the live Rubric cannot silently change what this run measured.
"""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from generator import model

SCHEMA = {"type": "object",
          "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5},
                         "synopsis": {"type": "string"}},
          "required": ["score", "synopsis"], "additionalProperties": False}

items = json.loads((HERE / "items-all.json").read_text())
scores = json.loads((HERE / "scores-c.json").read_text())
todo = [i for i, x in enumerate(scores) if x is None]
if not todo:
    print("scores-c.json is complete")
    sys.exit(0)

system = (ROOT / "prompt.md").read_text().replace(
    "{{RUBRIC}}", (HERE / "rubric-c.md").read_text().rstrip())
lock = threading.Lock()
def log(msg):
    with lock: print(f"  {msg}", flush=True)
client = model.Client(log)

def one(i):
    it = items[i]
    scores[i] = client.complete(
        system, f"Title: {it['title']}\nText: {it['synopsis']}",
        SCHEMA, "enrichment", it["title"][:40])

print(f"{len(todo)} Items still unscored ({sum(1 for i in todo if items[i]['source']=='control')} of them controls)")
# Two in flight, not four: the whole reason this file exists is a rate limit.
with ThreadPoolExecutor(max_workers=2) as ex:
    list(ex.map(one, todo))
(HERE / "scores-c.json").write_text(json.dumps(scores, indent=1))
still = sum(1 for x in scores if x is None)
print(f"refilled {len(todo) - still}, still unscored {still}")
