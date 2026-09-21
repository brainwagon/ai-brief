"""Spike: score the recorded calibration day with Jev, and compare.

Throwaway. Nothing here is imported by the generator, and nothing here writes
outside `calibration/jev-spike/`.

Two passes over the same 200 Items in
`calibration/2026-09-06-retune/items-all.json` (188 real ones plus 12 controls,
which are excluded from every comparison):

- a `score` question asks Jev to place the Item on a five-level ladder built
  from `rubric.md`;
- three `noul` questions ask Jev for the Rubric's named binary facts — is it a
  derivative artefact, is it marketing or money news, is it a benchmark.

The Rubric's explicit arithmetic is then applied in Python, because Jev answers
its questions independently and in parallel: the `score` answer cannot see the
noul answers, so the combination is ours. Two further nouls — `paper` and
`finding_travels`, for the Rubric's paper rule — were tried and removed; see
`adjust`. `sub_1b` is detected with the same regex the calibration check uses,
not asked of Jev, which cannot count.

Jev is a decision model, not a chat model, so this does NOT go through
`generator/model.py`. It POSTs to the System One endpoint. It also cannot write
the Synopsis, which is why the spike covers only the classify-and-score half.

    .venv/bin/python calibration/jev-spike/score.py            # fill missing, then report
    .venv/bin/python calibration/jev-spike/score.py --limit 4  # smoke test
    .venv/bin/python calibration/jev-spike/score.py --report   # report only
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
RETUNE = HERE.parent / "2026-09-06-retune"
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from generator import config

ENDPOINT = "https://openrouter.ai/api/v1/systemone"
MODEL = "typesafe/jev-1.13"
TRANSIENT = (429, 500, 502, 503, 504)
THRESHOLD = 0.5

ITEMS_FILE = RETUNE / "items-all.json"
DEEPSEEK_FILE = RETUNE / "scores-ds-f.json"
QUESTIONS_FILE = HERE / "questions.json"
OUT_FILE = HERE / "scores-jev.json"

# Both regexes are copied from calibration/2026-09-06-retune/check-editions.py,
# where their shapes are explained: the derivative one matches a repo id, not a
# title in general, and the size one demands a parameter word next to the number.
DERIVATIVE = re.compile(
    r"^[\w.-]+/[\w.-]*"
    r"(GGUF|AWQ|GPTQ|NVFP4|FP8|MLX|EXL2|[QK]\d_[KM]|bnb-4bit|int4|int8|-4bit|-8bit)",
    re.I,
)
SUB1B = re.compile(
    r"\b(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)[\s-]*(param|parameter|weights?\b)"
    r"|\b(param|parameter)\w*[\s:-]*(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)\b",
    re.I,
)


def questions():
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def noul_names():
    return [k for k, v in questions().items() if v.get("type") == "noul"]


def sub_1b(title, text):
    """The Rubric's stated-size rule, detected rather than asked of Jev."""
    return bool(SUB1B.search(f"{title} {text}"))


def adjust(record):
    """Apply the Rubric's explicit arithmetic to the base Score, in its order.

    Only the three rules that earned their place by measurement are applied. A
    fourth and fifth — a paper cap gated on whether its finding travels — were
    tried and removed: they made agreement worse, because the Rubric's paper rule
    is a judgement rather than a fact, and asking Jev for it as a yes/no left
    over half the pool uncertain at the threshold.

    A derivative artefact is never boosted by the sub-1B point — the Rubric says
    that point does not apply to a quantised re-upload — which is why the
    derivative cap returns before the boost is considered.
    """
    base = record.get("level")
    if base is None:
        return None
    noul = record.get("noul") or {}

    def yes(name):
        return (noul.get(name) or 0.0) >= THRESHOLD

    if yes("marketing"):
        return 1
    if yes("derivative"):
        return max(1, min(base, 2))
    if yes("benchmark"):
        return max(1, min(base, 2))
    if record.get("sub_1b"):
        return min(base + 1, 4)
    return base


def ask(state, qs, log, timeout=90.0, attempts=3):
    """One System One request. Returns the whole body, or None."""
    key = os.environ.get(config.OPENROUTER_KEY_ENV, "").strip()
    if not key:
        raise SystemExit(f"{config.OPENROUTER_KEY_ENV} is unset")
    payload = {"model": MODEL, "state": state, "questions": qs}
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.SITE_URL,
        "X-Title": "ai-brief",
    }
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                ENDPOINT, headers=headers, json=payload,
                timeout=(config.OPENROUTER_CONNECT_TIMEOUT, timeout),
            )
        except requests.exceptions.RequestException as exc:
            log(f"transport fault: {type(exc).__name__}")
        else:
            if response.status_code in TRANSIENT:
                log(f"HTTP {response.status_code}; retrying")
            elif response.status_code != 200:
                log(f"HTTP {response.status_code}: {response.text[:200]}")
                return None
            else:
                body = response.json()
                if body.get("error"):
                    log(f"error: {str(body['error'])[:160]}")
                elif body.get("answers"):
                    return body
                else:
                    log(f"no answers: {response.text[:160]}")
        if attempt < attempts:
            time.sleep(config.OPENROUTER_BACKOFF * attempt)
    return None


def interpret(answers, title, text):
    """One Item's answers into a flat record, then apply the adjustment."""
    score = answers.get("score") or {}
    mean = score.get("score")
    if not isinstance(mean, (int, float)):
        return None
    record = {
        "mean": mean,
        "level": round(mean) + 1,
        "confidence": score.get("confidence"),
        "noul": {},
        "sub_1b": sub_1b(title, text),
    }
    for name in noul_names():
        answer = answers.get(name) or {}
        probability = answer.get("noul")
        record["noul"][name] = probability if isinstance(probability, (int, float)) else None
    record["adjusted"] = adjust(record)
    return record


def run(limit, log):
    items = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    qs = questions()
    if limit:
        items = items[:limit]
    results = (
        json.loads(OUT_FILE.read_text(encoding="utf-8"))
        if OUT_FILE.exists() else [None] * len(items)
    )
    if len(results) != len(items):
        results = [None] * len(items)

    todo = [i for i, r in enumerate(results) if r is None]
    if not todo:
        log(f"all {len(items)} already scored")
        return results

    lock = threading.Lock()
    spent = [0.0]

    def safe_log(message):
        with lock:
            print(f"  {message}", flush=True)

    def one(index):
        item = items[index]
        state = f"Title: {item['title']}\nText: {item.get('synopsis', '')}".strip()
        body = ask(state, qs, safe_log)
        if body is None:
            return
        record = interpret(body.get("answers") or {}, item["title"],
                           item.get("synopsis", ""))
        if record is None:
            return
        with lock:
            spent[0] += (body.get("usage") or {}).get("cost") or 0.0
        results[index] = record

    started = time.time()
    done = 0

    def work(index):
        nonlocal done
        one(index)
        with lock:
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)} ({time.time() - started:.0f}s)",
                      flush=True)

    with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as pool:
        list(pool.map(work, todo))

    OUT_FILE.write_text(json.dumps(results, indent=1), encoding="utf-8")
    filled = sum(1 for r in results if r is not None)
    log(f"scored {filled}/{len(items)} in {time.time() - started:.0f}s, "
        f"${spent[0]:.4f} -> {OUT_FILE.name}")
    return results


def compare(name, a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        print(f"  {name}: nothing to compare")
        return
    n = len(pairs)
    exact = sum(1 for x, y in pairs if x == y)
    within = sum(1 for x, y in pairs if abs(x - y) <= 1)
    mae = sum(abs(x - y) for x, y in pairs) / n
    print(f"  {name}: n={n}  exact={exact / n:.0%}  within-1={within / n:.0%} "
          f" MAE={mae:.2f}")


def confusion(name, rows, cols, a, b):
    grid = [[0] * len(cols) for _ in rows]
    for x, y in zip(a, b):
        if x in rows and y in cols:
            grid[rows.index(x)][cols.index(y)] += 1
    print(f"  {name} (rows vs columns)")
    print("      " + "".join(f"{c:>6}" for c in cols))
    for value, line in zip(rows, grid):
        print(f"    {value} " + "".join(f"{cell:>6}" for cell in line))


def report():
    items = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    jev = json.loads(OUT_FILE.read_text(encoding="utf-8"))
    deepseek = json.loads(DEEPSEEK_FILE.read_text(encoding="utf-8"))
    if len(jev) != len(items):
        raise SystemExit("scores-jev.json does not line up with items-all.json")

    names = noul_names()
    rows = [
        {
            "title": items[i]["title"],
            "source": items[i]["source"],
            "human": items[i]["recorded"],
            "raw": jev[i]["level"] if jev[i] else None,
            "adjusted": jev[i]["adjusted"] if jev[i] else None,
            "noul": jev[i]["noul"] if jev[i] else {},
            "sub_1b": jev[i]["sub_1b"] if jev[i] else None,
            "ds": deepseek[i]["score"] if deepseek[i] else None,
        }
        for i in range(len(items))
        if items[i]["source"] != "control"
    ]

    def column(key, predicate=None):
        return [r[key] for r in rows if predicate is None or predicate(r)]

    scored = [r for r in rows if r["raw"] is not None]
    human = column("human")
    raw = column("raw")
    adjusted = column("adjusted")
    ds = column("ds")

    print(f"\n{len(rows)} real Items (controls excluded), {len(scored)} scored by Jev")
    print("\nAgreement with the human reference")
    compare("Jev raw (mean->round) ", raw, human)
    compare("Jev adjusted          ", adjusted, human)
    compare("deepseek-v4-flash     ", ds, human)

    print("\nItems at or above the cutoff (Score >= 3)")
    for label, values in (("human", human), ("deepseek", ds),
                          ("Jev raw", raw), ("Jev adjusted", adjusted)):
        passing = sum(1 for x in values if x is not None and x >= 3)
        print(f"  {label:<14} {passing:>3} / {sum(1 for x in values if x is not None)}")

    print("\nConfusion, Jev adjusted over human")
    confusion("Jev adjusted x human", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], adjusted, human)

    print("\nNoul prevalence at the 0.5 threshold")
    for name in names:
        values = [r["noul"].get(name) for r in rows if r["noul"].get(name) is not None]
        yes = sum(1 for v in values if v >= THRESHOLD)
        print(f"  {name:<16} yes {yes:>3} / {len(values)}")
    small = sum(1 for r in rows if r["sub_1b"])
    print(f"  {'sub_1b (regex)':<16} yes {small:>3} / {len(rows)}")

    print("\nThreshold sensitivity (noul probability in 0.35-0.65; the rest move nothing)")
    for name in names:
        values = [r["noul"].get(name) for r in rows if r["noul"].get(name) is not None]
        near = sum(1 for v in values if 0.35 <= v <= 0.65)
        print(f"  {name:<16} {near:>3} / {len(values)}")

    print("\nWhat the derivative rule fired on (highest probability first)")
    fired = sorted(
        (r for r in rows if (r["noul"].get("derivative") or 0) >= THRESHOLD),
        key=lambda r: -r["noul"]["derivative"],
    )
    for r in fired[:12]:
        print(f"  {r['noul']['derivative']:.2f}  raw {r['raw']} -> {r['adjusted']}  "
              f"{r['title'][:58]}")
    print(f"  ... {len(fired)} fired in total; eyeball for datasets and repos "
          f"that are not model re-uploads")

    changed = [r for r in rows
               if r["raw"] is not None and r["raw"] != r["adjusted"]]
    print(f"\nItems the adjustment moved: {len(changed)}")
    for name in names:
        fired = [r for r in changed if (r["noul"].get(name) or 0) >= THRESHOLD]
        if fired:
            print(f"  {name:<16} {len(fired):>3}")
    boosted = [r for r in changed if r["sub_1b"]]
    if boosted:
        print(f"  {'sub_1b (boost)':<16} {len(boosted):>3}")

    by_source = {}
    for r in rows:
        if r["adjusted"] is None:
            continue
        stat = by_source.setdefault(r["source"], [0, 0, 0, 0])
        stat[0] += 1
        if r["adjusted"] == r["human"]:
            stat[1] += 1
        if abs(r["adjusted"] - r["human"]) <= 1:
            stat[2] += 1
        stat[3] += abs(r["adjusted"] - r["human"])
    print("\nPer Source, Jev adjusted vs human")
    print("    source                 n  exact  within-1  MAE")
    for source, (n, exact, within, total) in by_source.items():
        print(f"    {source:<20} {n:>3}  {exact / n:>5.0%}  {within / n:>7.0%}  "
              f"{total / n:>4.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if not args.report:
        run(args.limit, print)
    if not args.limit:
        report()


if __name__ == "__main__":
    main()
