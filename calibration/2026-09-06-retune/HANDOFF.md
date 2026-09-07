# Handoff — the sub-1B retune, one Edition in

Updated 2026-09-07, after the first Edition the changed Rubric scored.
Written 2026-09-06; the original framing is in the commit history.

Pick this up around **2026-09-14**. Not 2026-09-10 — see *How long this needs*.

## Where things stand

The Rubric prefers language models under 1B parameters, both announcements and
first-hand accounts of running one. `pick-prompt.md` puts such an Item first
among the Picks. All of it is on `main`. The timer runs at 06:00 daily.

Editions dated **2026-09-07 and later** are scored by the changed Rubric.
2026-09-06 and earlier are the "before" side.

## Run this first

    .venv/bin/python calibration/2026-09-06-retune/check-editions.py 2026-08-31

Everything below is read off that output.

## What the first Edition says

    Edition      Items Picks   Scores        derivative  sub-1B
    2026-09-06      14     3   3:8 4:6              0       0     <- last old Edition
    2026-09-07      25     4   3:11 4:14            1       0     <- first new one

**Question 1 — has the Score 4 gone? No, and this was the real worry.** The pool
test predicted 4s falling from 12 to 6 out of 188. The page came back 14 Items at
4 out of 25 — 56%, against 60% across the eight Editions. The Brief is still a
page of 4s. A full 25-Item Edition with 4 Picks is an ordinary good day. Keep
watching the `Scores` column, but the collapse did not happen.

**Question 2 — are sub-1B Items arriving? Not yet, and this is the open one.**
The first Edition under the new Rubric published **none**. The clause has not had
an occasion to fire.

**Question 3 — the derivative defect. Two in eight Editions.**
`orcarouter/GLM-5.3-Flash-Uncensored-FP8` on 09-01 and
`dealignai/GLM-5.3-CYBERSECURITY-FP8` on 09-07, both at Score 3. Note that both
are re-uploads of a model far **over** 1B, so the size rule is not what carried
them — this is the plain derivative rule leaking on its own, and it predates the
retune. Still worth counting, but it is not evidence about the sub-1B change.

## How long this needs

Longer than I said on 2026-09-06. Correcting the check (below) dropped the count
of genuine sub-1B Items across eight Editions from about one a day to **one**:
`sanoTTS`, 294k parameters, on 09-04, and that was under the *old* Rubric.
`LatentPress` on 09-04 also states a count under 1B, but it is a 4.2M-26.2M
adapter on a frozen model rather than a small model, so a human should decide
whether it counts at all.

At roughly one clean Item a week, three days of Editions cannot answer question
2. Give it a week or two, and judge on a handful of Items rather than the first
one that appears.

## Two mistakes in the check, both now fixed

Recorded because both inflated the evidence in the direction I wanted, and the
next person should distrust this script the same way.

1. **The sub-1B pattern matched any number followed by M.** It counted "1M-token
   context windows" and "240M domain names" as model sizes. On 2026-09-07 it
   reported a sub-1B Item where the page had none. The number must now sit next
   to a parameter word.
2. **The Pick counter split on the first `</section>`** and swept in the Edition
   nav, reporting six Picks on a page showing four — and the Pick pass can never
   return more than four, which is what gave it away. It now reads the Picks
   section only.

An earlier version had a third fault of the same kind, described in `edc4578`: it
matched derivative artefacts against the Synopsis and flagged 21 Items, 20 of
which were first-hand reports of somebody *running* a quantised model — which the
Rubric wants.

## Still never measured

- **`pick-prompt.md`.** The Pick pass has never been run in testing. Whether a
  sub-1B Item is Picked first is unverified, and cannot be verified until
  question 2 produces an Item.
- **Four of the six sub-1B controls are worthless.** `handson`, `paper`, `repo`
  and `ceiling` score 4.8-5.0 under the *baseline* Rubric, so there is no
  headroom for a point to show in. Only `release/sub1b` and the paired gaps
  measure anything. Replace those four before reusing the controls.

## If the answer is "put it back"

`rubric-old.md` here is the Rubric at 2a8113e. The sub-1B change is two passages:
a sentence on **Small and local**, and a clause on **Scale is not merit**. Both
lift out cleanly.

Reverting `rubric.md` wholesale would also undo the parallel rewrite of the same
day — tightened 3 and 5 paragraphs, popularity demoted, the paper rule. Those
were somebody else's decisions and are not mine to guess at.
