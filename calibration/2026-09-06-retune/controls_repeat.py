"""The controls, five draws each, because one draw per control decides nothing.

The 188-Item counts are averages over many Items and are stable enough to read
directly. A control is a single Item, so a one-off ±1 there is indistinguishable
from the rule working, which is exactly the question. Five draws per control per
rubric, same model the generator now uses.
"""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from generator import config, model

REPS = 5
RUBRICS = {"old": "rubric-old.md", "c": "rubric-c.md",
           "d": "rubric-d.md", "e": "rubric-e.md", "f": "rubric-f.md"}
SCHEMA = {"type": "object",
          "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5},
                         "synopsis": {"type": "string"}},
          "required": ["score", "synopsis"], "additionalProperties": False}

items = json.loads((HERE / "items-all.json").read_text())
ctl = [it for it in items if it["source"] == "control"]
prompt = (ROOT / "prompt.md").read_text()
out = HERE / "controls-repeat.json"
data = json.loads(out.read_text()) if out.exists() else {}

lock = threading.Lock()
def log(m):
    with lock: print(f"  {m}", flush=True)
client = model.Client(log, model=config.OPENROUTER_MODEL)

jobs = []
for tag, rf in RUBRICS.items():
    system = prompt.replace("{{RUBRIC}}", (HERE / rf).read_text().rstrip())
    for it in ctl:
        key = f"{tag}|{it['title'][:40]}"
        have = len(data.get(key, []))
        for _ in range(REPS - have):
            jobs.append((key, system, it))

print(f"{len(jobs)} draws to make", flush=True)
def one(job):
    key, system, it = job
    got = client.complete(system, f"Title: {it['title']}\nText: {it['synopsis']}",
                          SCHEMA, "enrichment", it["title"][:40])
    if got:
        with lock:
            data.setdefault(key, []).append(got["score"])
with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as ex:
    list(ex.map(one, jobs))
out.write_text(json.dumps(data, indent=1))
print("done", flush=True)
