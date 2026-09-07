"""The same comparison again, under the model that now scores real Editions.

`nemotron-nano-9b` scored everything in `scores-old2/new2/c.json`; the generator
moved to `deepseek/deepseek-v4-flash` on 2026-09-06. This re-runs the baseline
Rubric and the shipped one over the same 200 Items under DeepSeek, so the
question answered is about the scorer that actually runs. The emphatic draft is
not re-run — it was rejected, and re-measuring it would only re-confirm a
decision already taken.

Idempotent per rubric: an existing output file is left alone. Null entries are
refilled by running this again.
"""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from generator import config, model

MODEL = config.OPENROUTER_MODEL   # deliberately live: the point is today's scorer
SCHEMA = {"type": "object",
          "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5},
                         "synopsis": {"type": "string"}},
          "required": ["score", "synopsis"], "additionalProperties": False}

items = json.loads((HERE / "items-all.json").read_text())
prompt = (ROOT / "prompt.md").read_text()

def score(tag, rubric_file):
    out = HERE / f"scores-ds-{tag}.json"
    results = json.loads(out.read_text()) if out.exists() else [None] * len(items)
    todo = [i for i, x in enumerate(results) if x is None]
    if not todo:
        print(f"{tag}: complete"); return results
    system = prompt.replace("{{RUBRIC}}", (HERE / rubric_file).read_text().rstrip())
    lock = threading.Lock()
    def log(m):
        with lock: print(f"[{tag}] {m}", flush=True)
    client = model.Client(log, model=MODEL)
    def one(i):
        it = items[i]
        results[i] = client.complete(system, f"Title: {it['title']}\nText: {it['synopsis']}",
                                     SCHEMA, "enrichment", it["title"][:40])
    with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as ex:
        list(ex.map(one, todo))
    out.write_text(json.dumps(results, indent=1))
    print(f"{tag}: scored {len(todo) - sum(1 for x in results if x is None)}/{len(todo)}, "
          f"unscored {sum(1 for x in results if x is None)}", flush=True)
    return results

print(f"model: {MODEL}, {len(items)} Items x 2 rubrics", flush=True)
score("old", "rubric-old.md")
score("c", "rubric-c.md")
score("d", "rubric-d.md")
score("e", "rubric-e.md")
score("f", "rubric-f.md")   # the live rubric.md as rewritten 2026-09-06
