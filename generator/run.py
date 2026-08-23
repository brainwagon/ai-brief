"""One Run: gather, Enrich, Pick, select, and Generate.

A Run writes files and NEVER touches git. `publish.sh` does the commit and the
push, so a git failure stays distinguishable from a generation failure
(map note 11, and CONTEXT.md's split between Generate and Publish).

    .venv/bin/python -m generator.run

Exit status is 0 when an Edition was written, 1 when it was not.
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, enrichment, pick, render, select, sources
from .render import EDITION_RE
from .snapshot import SnapshotStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate one Edition of the Brief.")
    parser.add_argument(
        "--docs-dir", type=Path, default=config.DOCS_DIR,
        help="where the Edition and the Index are written",
    )
    parser.add_argument(
        "--state-dir", type=Path, default=config.STATE_DIR,
        help="where the Snapshots live",
    )
    parser.add_argument(
        "--openrouter-base", default=config.OPENROUTER_BASE,
        help="override for exercising the Unenriched path against a dead endpoint",
    )
    parser.add_argument(
        "--only", default=None,
        help="comma-separated Source keys, for exercising one Source",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="revise an Edition that already exists for this date",
    )
    parser.add_argument(
        "--date", default=None,
        help="override the Edition's date (YYYY-MM-DD); defaults to the Run's UTC date",
    )
    args = parser.parse_args(argv)

    started = time.time()

    def log(message):
        elapsed = time.time() - started
        print(f"[{elapsed:6.1f}s] {message}", flush=True)

    # All times are UTC internally. The Edition's date is one string, used in
    # the filename, the URL, the <time datetime> and — reformatted only for the
    # visible heading — the <h1>.
    run_at = datetime.now(timezone.utc)
    run_date = args.date or run_at.strftime("%Y-%m-%d")

    keys = config.SOURCE_ORDER
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip()]

    log(f"Run for {run_date} ({run_at.strftime('%H:%M:%S')} UTC)")

    # An Edition is published once and never revised (CONTEXT.md). A second Run
    # on the same date would find every Item already in the Snapshots and write
    # an empty page over a good one, so it stops here instead. A deliberate
    # retry after a failed Run passes --force.
    existing = args.docs_dir / f"{run_date}.html"
    if existing.exists() and not args.force:
        log(f"{existing.name} already exists; an Edition is never revised. "
            f"Pass --force to write it again.")
        return 0

    # --- gather -----------------------------------------------------------
    store = SnapshotStore(args.state_dir)
    log("Gathering:")
    results = {}
    for key in keys:
        result = sources.gather(key, run_at, log)
        results[key] = result

    # --- the Snapshot diff ------------------------------------------------
    #
    # An Item is new when its Identity is absent from the retained Snapshots.
    # Every Source gets one. Four of them have no other novelty signal at all;
    # for the three with real timestamps the Snapshot only stops a second Run
    # republishing what the first already carried.
    log("Snapshot diff:")
    for key, result in results.items():
        if result.unavailable:
            continue
        known = store.known(key)
        before = len(result.items)
        result.items = [i for i in result.items if i.identity not in known]
        for position, item in enumerate(result.items):
            item.rank = position
        log(f"  {key}: {len(result.items)} new of {before} candidates "
            f"({len(known)} Identities known)")

    dropped = select.dedup_papers(results)
    if dropped:
        log(f"  arXiv: {dropped} Items dropped as Hugging Face papers key collisions")
    for result in results.values():
        result.considered = len(result.items)

    # --- Enrichment -------------------------------------------------------
    to_enrich = [item for result in results.values() for item in result.items]
    log(f"Enrichment: {len(to_enrich)} Items")
    model_up = enrichment.reachable(log, base=args.openrouter_base)
    if model_up and to_enrich:
        enrichment.enrich_all(to_enrich, log, base=args.openrouter_base)
    elif not model_up:
        log("  skipped — the Edition publishes with every Item Unenriched")

    # The Score distribution per Source is what rubric drift will be read from
    # later, so a Run states it rather than leaving it to be reconstructed.
    for key in keys:
        result = results[key]
        if result.unavailable or not result.items:
            continue
        counts = [
            sum(1 for i in result.items if i.score == score) for score in range(1, 6)
        ]
        log("  %s: Scores 1-5 = %s, %d at or above the cutoff, %d Unenriched"
            % (key, "/".join(str(c) for c in counts),
               sum(counts[config.CUTOFF - 1:]),
               sum(1 for i in result.items if i.unenriched)))

    # --- selection --------------------------------------------------------
    select.select(results)
    chosen = [item for result in results.values() for item in result.items]
    log(f"Selected {len(chosen)} Items for the Edition")

    # --- Picks ------------------------------------------------------------
    picks = pick.choose(chosen, log, base=args.openrouter_base) if model_up else []

    # --- Generate ---------------------------------------------------------
    args.docs_dir.mkdir(parents=True, exist_ok=True)
    previous = _previous_edition(args.docs_dir, run_date)
    model_down = not model_up
    page, counts = render.edition(run_date, results, picks, model_down, previous)
    edition_path = args.docs_dir / f"{run_date}.html"
    edition_path.write_text(page, encoding="utf-8")
    log(f"Wrote {edition_path}")

    _update_index(args.docs_dir, args.state_dir, run_date, counts, picks, chosen, log)

    # Snapshot writes happen on success only. An Unavailable Source keeps its
    # previous Snapshot untouched, so the next successful Run still sees the
    # right "new" set rather than treating a whole Source as newly appeared.
    for key, result in results.items():
        if result.unavailable:
            log(f"  {key}: Unavailable, previous Snapshot carried forward")
            continue
        store.record(key, run_date, result.seen)
    log("Snapshots written")

    log(
        "Done: %d Items, %d Picks, %d Unavailable, %d Unenriched, %.1fs wall clock"
        % (
            counts["items"],
            counts["picks"],
            counts["unavailable"],
            counts["unenriched"],
            time.time() - started,
        )
    )
    return 0


def _previous_edition(docs_dir, run_date):
    dates = sorted(
        match.group(1)
        for match in (EDITION_RE.match(p.name) for p in docs_dir.glob("*.html"))
        if match
    )
    earlier = [d for d in dates if d < run_date]
    return earlier[-1] if earlier else None


def _update_index(docs_dir, state_dir, run_date, counts, picks, chosen, log):
    editions = [r for r in render.load_editions(state_dir) if r.get("date") != run_date]

    teaser = None
    if picks:
        teaser = picks[0].title
    else:
        scored = [i for i in chosen if i.score is not None]
        if scored:
            teaser = max(scored, key=lambda i: (i.score, -i.rank)).title

    record = dict(counts)
    record["date"] = run_date
    if teaser:
        record["teaser"] = teaser
    editions.append(record)
    editions.sort(key=lambda r: r["date"], reverse=True)
    render.save_editions(state_dir, editions)

    index_path = docs_dir / "index.html"
    index_path.write_text(
        render.index(index_path.read_text(encoding="utf-8"), editions),
        encoding="utf-8",
    )
    log(f"Wrote {index_path} ({len(editions)} Editions listed)")


if __name__ == "__main__":
    sys.exit(main())
