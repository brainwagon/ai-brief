# ai-brief

A daily Brief of what is new in AI, gathered from eight Sources — arXiv, Hacker
News, GitHub New Repos, dev.to, r/LocalLLaMA, and Hugging Face's models,
datasets and papers — scored and summarised by a free model hosted on
OpenRouter, and published to GitHub Pages at
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

Useful flags for exercising the degraded paths by hand: `--docs-dir` and
`--state-dir` write somewhere other than the repo, `--openrouter-base` can be
pointed at a dead endpoint to see an all-Unenriched Edition — as can unsetting
`OPENROUTER_API_KEY` — `--only` gathers a subset of Sources, and `--date`
overrides the Edition's date.

## The model

Enrichment and the Pick pass go to OpenRouter, using free models only. The key
is read from `OPENROUTER_API_KEY`; an unattended Run gets it from
`~/.config/ai-brief/env`, which both `publish.sh` and the systemd unit read,
because neither sources a shell profile. With no key the Run still produces an
Edition and says on the page that every Item is Unenriched.

The model and its fallbacks are pinned in `generator/config.py`. Free models
are rate-limited upstream without warning, so more than one is listed and
OpenRouter walks the list itself.

## Layout

| path | what it is |
|---|---|
| `generator/` | the generator; writes files, never runs git |
| `generator/sources/` | one module per upstream, eight Sources in all |
| `generator/model.py` | the one call to OpenRouter, shared by Enrichment and Picks |
| `publish.sh` | the wrapper that commits and pushes |
| `rubric.md` | the Rubric — what a Score of 1 to 5 means. Edit this. |
| `prompt.md` | the Prompt wrapped around it, with a `{{RUBRIC}}` placeholder |
| `pick-prompt.md` | the second pass that chooses the day's Picks |
| `docs/` | what GitHub Pages serves: the Index, the stylesheet, every Edition |
| `state/` | the Snapshots, committed on purpose, on a rolling 30-day window |
| `prototype/example-edition.html` | the markup contract, outside `docs/` so it is never served |
| `calibration/` | the recorded Scores a Rubric was tuned against |

Dependencies are `requests` and `beautifulsoup4` and nothing else; everything
else is the standard library, on purpose. Python 3.10 in `.venv`.
