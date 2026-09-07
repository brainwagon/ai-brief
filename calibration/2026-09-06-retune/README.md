# Retune of 2026-09-06 — calling out sub-1B models

Working files for the rubric change that added the sub-1B preference. Scored
against the 188 Items of `calibration/2026-08-17.md`, using each Item's recorded
title and Synopsis as the `Title:`/`Text:` input, because the original abstracts
were never kept. **Not a replication of that day**: different input text, and
`nvidia/nemotron-nano-9b-v2` in place of `gemma4:e4b`. Every rubric here was
scored in the same sitting, so old-against-new is the only comparison the
numbers support.

- `rubric-old.md` — the Rubric as committed at 2a8113e, the baseline.
- `rubric-c.md` — what shipped to `rubric.md`. Kept apart from the live file so a
  later edit cannot change what this run measured.
- `controls.json` — 12 injected Items: sub-1B releases and hands-on reports, each
  paired with a near-identical larger twin, plus four traps (a 1.7B near-miss, a
  `tiny/mini/nano` name with no stated size, a GGUF re-upload, a funding story).
- `items-all.json` — the 188 parsed Items followed by the 12 controls, in the
  order every `scores-*.json` uses.
- `scores-old.json` — baseline, 188 Items only (the first run, before controls).
- `scores-old2.json`, `scores-new2.json`, `scores-c.json` — 200 entries each:
  baseline, the discarded emphatic draft, and the shipped version.
- `rescore2.py` — the full harness. `fill.py` — refills only the null entries.

## What it found

Items at or above the cutoff, of the 165 all three rubrics scored:

| rubric | >=3 | 4s |
|---|---|---|
| baseline | 36 | 3 |
| emphatic draft | 9 | 0 |
| shipped | 29 | 2 |

The emphatic draft is the one that failed. Twenty-odd lines saying one narrow
category is the reader's favourite *above all* made everything outside it read as
comparatively unworthy, and the whole distribution slid a point: 50 Items at or
above the cutoff became 12, and no Item anywhere scored 4. Restoring the 4 and 5
paragraphs verbatim did not fix it, which is what ruled out the scale rewrite and
left the framing itself. The shipped version says the same thing in two sentences
and leaves arXiv and GitHub New Repos unmoved.

Run-to-run noise on this harness is about ±7: the baseline Rubric scored 43 and
then 50 on two identical passes over the same 188 Items.

## Unfinished

OpenRouter's free-tier daily limit ran out mid-run. **All 12 controls and 22 HF
Papers Items are unscored under the shipped version**, so the shipped version is
known not to wreck the rest of the day and is *not* yet known to give a sub-1B
Item its point. That is the claim the controls exist to test.

    .venv/bin/python calibration/2026-09-06-retune/fill.py

Run it until it prints `scores-c.json is complete` — about 35 calls — then diff
the controls against `scores-old2.json`. Under the emphatic draft the sub-1B arms
moved +1 while their larger twins moved -1 and -2; the shipped version should
separate the pairs the same way, and must leave the four traps alone.

## The model moved out from under this run

Later on 2026-09-06 the generator was switched from the free
`nvidia/nemotron-nano-9b-v2` to a paid `deepseek/deepseek-v4-flash`. Every score
in every `scores-*.json` here was drawn from the free model, so `fill.py` and
`rescore2.py` now **pin it explicitly** rather than reading
`config.OPENROUTER_MODEL` — refilling the 35 gaps from DeepSeek would put two
different scorers in one file and destroy the comparison.

That pin keeps the half-finished run honest. It does not make it current: the
Rubric that scores real Editions from now on is being read by DeepSeek, and none
of the numbers above were measured against it. The rate limit that stopped this
run is also gone with the free tier, and a full three-rubric pass is now ~600
calls of a few seconds each for well under a dollar. Redoing the whole comparison
under DeepSeek is the better answer than finishing this one.

## The live Rubric, measured

`rubric.md` was rewritten in parallel on 2026-09-06, well beyond the sub-1B
clause — the 3 and 5 paragraphs were tightened, popularity was demoted from
tie-breaker to no evidence at all, and the size rule was given the two limits
this run had found missing: it does not apply to a derivative artefact, and it
cannot by itself make a 5. `rubric-f.md` is a copy of that file as measured, and
`scores-ds-f.json` its scores.

It is the best version of the five on the question this retune was about.

| rubric | >=3 of 188 | 4s | release lift | 1.7B | nano-name | GGUF |
|---|---|---|---|---|---|---|
| baseline | 53 | 12 | — | — | — | — |
| C | 42 | 14 | +0.8 | +0.4 | +0.4 | +1.6 |
| D | 33 | 7 | +0.8 | -1.2 | -0.6 | +1.2 |
| E | 42 | 8 | +0.6 | -0.2 | +0.6 | +1.4 |
| **live** | **37** | **6** | **+1.0** | **+0.2** | **+0.0** | **+0.8** |

Paired gaps, sub-1B minus its larger twin: baseline +0.6/+0.8/+0.2, live
+1.8/+1.0/+1.0 — the widest separation measured, D's precision without D's
across-the-board suppression.

The GGUF leak is halved but not closed: +0.8 where C leaked +1.6, still enough
to carry a re-upload over the cutoff on some draws, despite the clause now
naming derivatives explicitly. Whatever is happening there is not a matter of
phrasing, and it remains the open defect.

Six 4s against the baseline's twelve is the largest cost. That is mostly the
rewritten 3 and 5 paragraphs rather than the size rule, and it looks deliberate.
Worth watching in real Editions: with the cutoff at 3 the page still fills, but a
Brief whose top Score has nearly vanished is a different reading experience.
