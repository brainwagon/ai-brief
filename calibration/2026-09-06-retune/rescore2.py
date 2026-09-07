import json, re, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, "/home/markv/ai-brief")
from generator import config, model
ROOT = Path("/home/markv/ai-brief"); SCRATCH = Path(__file__).resolve().parent
SCHEMA = {"type":"object","properties":{"score":{"type":"integer","minimum":1,"maximum":5},"synopsis":{"type":"string"}},"required":["score","synopsis"],"additionalProperties":False}

def parse_items():
    text = (ROOT / "calibration/2026-08-17.md").read_text()
    tail = text.split("## Every Item, with its Score and Synopsis", 1)[1]
    items, source, lines = [], None, tail.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("### "): source = line[4:].strip(); continue
        m = re.match(r"^- \*\*(\d)\*\* — (.*?)\s*$", line)
        if m:
            items.append({"source": source, "recorded": int(m.group(1)),
                          "title": m.group(2).strip(),
                          "synopsis": lines[i+1].strip() if i+1 < len(lines) else ""})
    return items

def system_for(p):
    return (ROOT/"prompt.md").read_text().replace("{{RUBRIC}}", Path(p).read_text().rstrip())

def run(tag, system, items):
    out = SCRATCH / f"scores-{tag}.json"
    if out.exists(): return json.loads(out.read_text())
    lock = threading.Lock(); results = [None]*len(items)
    def log(m):
        with lock:
            if "429" not in m and "502" not in m: print(f"[{tag}] {m}", flush=True)
    client = model.Client(log)
    def one(i):
        it = items[i]
        results[i] = client.complete(system, f"Title: {it['title']}\nText: {it['synopsis']}",
                                     SCHEMA, "enrichment", it["title"][:50])
        if i % 50 == 0: print(f"[{tag}] {i}/{len(items)}", flush=True)
    with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as ex:
        list(ex.map(one, range(len(items))))
    out.write_text(json.dumps(results, indent=1)); return results

items = parse_items()
ctrl = json.load(open("controls.json"))
for c in ctrl: c["source"] = "control"; c["recorded"] = 0
allit = items + ctrl
json.dump(allit, open("items-all.json","w"), indent=1)
run("old2", system_for(SCRATCH/"rubric-old.md"), allit)
run("c", system_for(SCRATCH/"rubric-c.md"), allit)
run("new2", system_for(ROOT/"rubric.md"), allit)
print("done", flush=True)
