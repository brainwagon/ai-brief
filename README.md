# ai-brief

A daily Brief of what is new in AI, gathered from nine Sources — arXiv, Hacker
News, GitHub New Repos, dev.to, r/LocalLLaMA, WIRED, and Hugging Face's models,
datasets and papers — scored by a decision model and summarised by a cheap
hosted model, both on OpenRouter, and published to GitHub Pages at
<https://mvandewettering.com/ai-brief/>.

The vocabulary is in [`CONTEXT.md`](CONTEXT.md) and the route is charted on the
[wayfinder map](../../issues?q=label%3Awayfinder%3Amap).

## Running it

    ./publish.sh

That is the whole thing, and it is what a systemd timer points at. It Generates,
then Publishes:

| exit | meaning |
|---|---|
| 0 | an Edition was Generated, and either Published or already current |
| 1 | the Run failed; nothing was committed and nothing was pushed |
| 2 | the Run succeeded but Publish failed; the Edition is on disk, uncommitted |

To Generate without Publishing — the generator never touches git:

    .venv/bin/python -m generator.run

A Run gathers the nine Sources, diffs them against yesterday's Snapshots, scores
every new Item with Jev, applies the cutoff and the per-Source ceiling, writes a
Synopsis for the survivors, chooses the Picks, and writes the Edition and the
Index.

Useful flags for exercising the degraded paths by hand: `--docs-dir` and
`--state-dir` write somewhere other than the repo, `--only` gathers a subset of
Sources, and `--date` overrides the Edition's date. `--decisions-base` points
the scoring stage at a dead endpoint to see an all-Unenriched Edition, and
`--openrouter-base` does the same for the Synopsis and the Picks; unsetting
`OPENROUTER_API_KEY` takes both down.

## The models

A Run puts Items to two different models, in two stages, and they fail
independently.

**Stage A — the Score, from Jev.** Every gathered Item is put to
`typesafe/jev-1.13`, a TypeSafe System One decision model reached through
OpenRouter's Decisions endpoint. It is not a chat model: it answers a typed
question set — Jev's position on a five-level ladder built from `rubric.md`, plus
a few `noul` questions that are the Rubric's named exceptions ("is this a
derivative artefact?", "is this marketing?") — and returns calibrated
probabilities rather than prose. The Rubric's arithmetic is then applied to
those answers and becomes the Score. The five levels are read straight out of
[`rubric.md`](rubric.md); the named exceptions and the arithmetic that applies
them live in [`jev-questions.json`](jev-questions.json). Neither fact is written
down twice, and tuning taste touches no code.

Every answer Jev returns is kept, and every Item it was shown is published in
the Edition's **Decisions** — a collapsed ledger at the foot of the page,
Selected or not, best Score first. Each row carries the Item's adjusted Score
beside the position and probabilities Jev gave, so the adjustment is visible.
It is the one table on the site, and the one place a bar is drawn.

**Stage B — the Synopsis, from a chat model.** After the cutoff and the ceiling
have run, the twenty-five or so surviving Items are put to a hosted chat model
for their Synopsis. Because the Score is already known, this Prompt is
synopsis-only and carries no Rubric. The model and its fallbacks are pinned in
`generator/config.py`, which also records what each was measured at; the paid
tier is deliberate, because the free ones answer this Prompt in about 23 seconds
a call and drop one in five, which is the difference between a Run that finishes
and one that hits the unit's 30-minute wall. Stage B bills a fraction of a cent;
Stage A is about a cent for the whole pool, in seconds. More than one model is
listed so that OpenRouter can walk the list when a provider is down; anything
added to it must accept a strict `json_schema` response format *and* tolerate
reasoning being switched off, since several otherwise-suitable endpoints refuse
the latter with a 400, which ends the Synopsis stage for the whole Run.

The key is read from `OPENROUTER_API_KEY`; an unattended Run gets it from
`~/.config/ai-brief/env`, which both `publish.sh` and the systemd unit read,
because neither sources a shell profile. With no key — or with no credit — the
Run still produces an Edition and says on the page what is missing: no Score if
Jev could not be reached, no Synopsis if the chat model could not.

## Layout

| path | what it is |
|---|---|
| `generator/` | the generator; writes files, never runs git |
| `generator/sources/` | one module per upstream, nine Sources in all |
| `generator/jev.py` | Stage A: the Jev call, and the Score's adjustment |
| `generator/synopsis.py` | Stage B: the Synopsis pass over the selected Items |
| `generator/model.py` | the chat call to OpenRouter, used by Stage B and the Picks |
| `publish.sh` | the wrapper that commits and pushes |
| `rubric.md` | the Rubric — what a Score of 1 to 5 means, and the single home of the taste |
| `jev-questions.json` | the Score's named exceptions and the arithmetic that applies them |
| `synopsis-prompt.md` | the Synopsis Prompt |
| `pick-prompt.md` | the second pass that chooses the day's Picks |
| `docs/` | what GitHub Pages serves: the Index, the stylesheet, every Edition |
| `state/` | the Snapshots, committed on purpose, on a rolling 30-day window |
| `prototype/example-edition.html` | the markup contract, outside `docs/` so it is never served |
| `calibration/` | the recorded Scores a Rubric was tuned against, and the `jev-spike` experiments behind Stage A |

Dependencies are `requests` and `beautifulsoup4` and nothing else; everything
else is the standard library, on purpose. Python 3.10 in `.venv`.
