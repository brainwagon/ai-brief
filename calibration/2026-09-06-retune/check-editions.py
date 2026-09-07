"""Read published Editions and report what the sub-1B retune actually did.

The retune was measured against a candidate pool, not against real Editions. This
reads `docs/*.html` — what was really published — and answers the three questions
the retune left open. Run it with no arguments for every Edition, or give it a
date to start from:

    .venv/bin/python calibration/2026-09-06-retune/check-editions.py 2026-09-01

The Rubric changed on 2026-09-06. Editions dated 2026-09-07 and later are the
first ones scored by it, so compare across that line.
"""
import re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"

# Derivative artefacts: the Rubric says a re-upload stays at 2 and so never
# reaches a page. Matched on the TITLE only, and only when it looks like a repo
# id — `owner/name-GGUF`. Matching the Synopsis as well caught every first-hand
# report of somebody RUNNING a quantised model, which the Rubric rewards on
# purpose and which is the exception the derivative rule already names.
DERIVATIVE = re.compile(r"^[\w.-]+/[\w.-]*"
                        r"(GGUF|AWQ|GPTQ|NVFP4|FP8|MLX|EXL2|[QK]\d_[KM]|"
                        r"bnb-4bit|int4|int8|-4bit|-8bit)", re.I)
# A stated PARAMETER count under 1B, which is what the new rule is meant to
# reward. The number must sit next to a parameter word: a bare "1M" matched
# "1M-token context windows" and "240M domain names", neither of which is a
# model size, and both of which were counted as evidence the rule was working.
SUB1B = re.compile(
    r"\b(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)[\s-]*"
    r"(param|parameter|weights?\b)"
    r"|\b(param|parameter)\w*[\s:-]*(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)\b",
    re.I)

ITEM = re.compile(
    r'<li class="([^"]*)" id="[^"]*">\s*'
    r'<h3 class="item-title"><a href="[^"]*">(.*?)</a></h3>(.*?)</li>',
    re.S)
SCORE = re.compile(r'<span class="score">Score (\d)</span>')
SYNOPSIS = re.compile(r'<p class="synopsis">(.*?)</p>', re.S)
SOURCE = re.compile(r'<h2 id="([^"]*)">([^<]*?) <span class="source-count">')

def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()

start = sys.argv[1] if len(sys.argv) > 1 else "0000-00-00"
pages = sorted(p for p in DOCS.glob("2*.html") if p.stem >= start)
if not pages:
    print("no Editions found"); sys.exit(1)

print(f"{'Edition':<12} {'Items':>5} {'Picks':>5}   Scores        derivative  sub-1B")
totals = Counter()
flagged, small = [], []
for page in pages:
    html = page.read_text()
    # Count the Picks inside the Picks section only. Splitting on the first
    # </section> swept in the Edition nav and reported six Picks where the page
    # showed four, and the Pick pass can never return more than four.
    m_picks = re.search(r'<section class="picks".*?</section>', html, re.S)
    picks = len(re.findall(r"<li>", m_picks.group(0))) if m_picks else 0
    dist, n_der, n_small = Counter(), 0, 0
    for m_item in ITEM.finditer(html):
        classes, title, rest = m_item.groups()
        m = SCORE.search(rest)
        if not m:
            dist["U"] += 1      # Unenriched: no Score on the page
            continue
        s = int(m.group(1)); dist[s] += 1; totals[s] += 1
        syn = strip(SYNOPSIS.search(rest).group(1)) if SYNOPSIS.search(rest) else ""
        clean = strip(title)
        if DERIVATIVE.search(clean):
            n_der += 1; flagged.append((page.stem, s, clean))
        if SUB1B.search(f"{clean} {syn}"):
            n_small += 1; small.append((page.stem, s, clean))
    shape = " ".join(f"{s}:{dist[s]}" for s in (1, 2, 3, 4, 5) if dist[s])
    u = f" U:{dist['U']}" if dist["U"] else ""
    print(f"{page.stem:<12} {sum(v for k,v in dist.items() if k!='U'):>5} "
          f"{picks:>5}   {shape+u:<14}{n_der:>8}  {n_small:>6}")

n = sum(totals.values())
print(f"\nacross {len(pages)} Edition(s), {n} scored Items:")
for s in (3, 4, 5):
    print(f"  Score {s}: {totals[s]:>3}  ({100*totals[s]//n if n else 0}%)")

print("\n--- derivative artefacts that reached a page (the open defect) ---")
print("\n".join(f"  {d}  Score {s}  {t[:80]}" for d, s, t in flagged) or "  none")
print("\n--- Items with a stated size under 1B (what the rule is for) ---")
print("\n".join(f"  {d}  Score {s}  {t[:80]}" for d, s, t in small) or "  none")
