# Handoff — The Decoder added as a tenth Source

Updated 2026-09-21. Nothing here is committed or published; it is all working
tree. `git status` shows four modified files and three new ones.

## Where things stand

The Decoder (`the-decoder.com`) is registered as the **tenth Source**. The
generator is otherwise unchanged and no Edition has been Regenerated.

The change, all on disk:

| file | what |
|---|---|
| `generator/sources/the_decoder.py` | new Source module (registered) |
| `generator/sources/arstechnica.py` | **draft, not registered** |
| `generator/sources/marktechpost.py` | **draft, not registered** |
| `generator/config.py` | `"the-decoder"` in `SOURCE_ORDER` (after `wired`) and `SOURCE_LABELS`; comment nine → ten |
| `generator/sources/__init__.py` | import + `FETCHERS` entry; docstring nine → ten |
| `CONTEXT.md` | **Source** now ten and names The Decoder; **Identity** now records the RSS `<guid>` form, and WIRED was added to that list too (it had been omitted) |
| `README.md` | the three "nine Sources" mentions |

The Decoder's Identity is its RSS `<guid>` (`https://the-decoder.com/?p=NNNNN`).
Its window is 72 hours, like WIRED's, and the Snapshot diff carries novelty.

**The first Run after this is committed will create `state/the-decoder.json`.**
Until then there is no Snapshot for it, so that Run will treat all ~10 Items as
new. That is correct, not a bug.

## Run this first

    .venv/bin/python - <<'PY'
    from generator import config, sources
    assert set(config.SOURCE_ORDER) == set(config.SOURCE_LABELS) == set(sources.FETCHERS)
    print(len(config.SOURCE_ORDER), "Sources consistent")
    PY

Then a cost-free end-to-end Generate, with the scoring endpoint pointed at a
dead port so no model is called:

    mkdir -p /tmp/brief-smoke/docs /tmp/brief-smoke/state
    cp docs/index.html docs/style.css /tmp/brief-smoke/docs/
    .venv/bin/python -m generator.run --docs-dir /tmp/brief-smoke/docs \
        --state-dir /tmp/brief-smoke/state --only the-decoder \
        --decisions-base http://127.0.0.1:9/ --date 2026-09-21

Expect: 10 gathered, 8 Selected (the `CEILING`), a `src-the-decoder` section,
and `item-the-decoder-…` anchors.

## Candidate sources that were checked

All fetched with the Brief's User-Agent on 2026-09-21.

| endpoint | result |
|---|---|
| `the-decoder.com/feed/` | **works** — rss 2.0, stable `<guid>`, ~10 items |
| `arstechnica.com/ai/feed/` | works — 20 items, only ~5 clear 72h |
| `marktechpost.com/feed/` | works — 10 items, mixes releases with listicles |
| `simonwillison.net/atom/everything/` | works — atom, 30 entries, many are one-line quotes |
| `feed.infoq.com/ai-ml-data-eng/` | works — 15 items, enterprise angle |
| `technologyreview.com/topic/artificial-intelligence/feed` | works, but diluted with non-AI |
| `deeplearning.ai/the-batch/feed/` | **dead** — 404 (and `/feed/` too) |
| `api.axios.com/feed/ai` | **dead** — 404 |
| `venturebeat.com/category/ai/feed/` | **429** to our User-Agent |

## Why only The Decoder

It was the only one adding a beat the existing nine lack rather than more of
what they already carry. On 2026-09-21 it had SoftBank's $11B OpenAI bond, the
US–China AI dialogue, an Epoch/Ipsos usage survey, and the Runway and Tencent
product moves — none of which arXiv/HN/GitHub/HF/WIRED would surface.

- **MarkTechPost** overlaps hardest: the model releases it writes up are what
  arXiv/HF papers already carry (Qwen-Image-2.1 appeared in both the same day),
  and it mixes in SEO listicles the Rubric has never had to judge.
- **Ars Technica AI** is good but thin (~5 in 72h) and skews security/policy,
  which is WIRED's corner.

Both remain as unregistered modules. Registering either is the same four edits
that were made for The Decoder, plus the "ten → eleven" wording.

## The open question: cross-source duplication

Deferred, not decided. The measurement on 2026-09-21:

- HN top-20 outbound links to tracked domains: 4 GitHub, 0 arXiv, 0 HF.
  Exactly **one** (`jaredpalmer/kev`) was also in GitHub New Repos.
- Press Items (WIRED + the three candidates): 33, with **two** same-story pairs
  at title-Jaccard ≥ 0.28 — Qwen-Image-2.1 (0.38) and the Gemini breach (0.29).

The analysis, so it need not be redone:

- The existing `select.dedup_papers` works because HF papers and arXiv **share a
  key form**, so it is a collision, not a guess (CONTEXT.md says so explicitly).
  `render.anchor` includes `item.source`, so a cross-source clash does **not**
  break the HTML — the rule is editorial only.
- Deterministic URL canonicalization (`arxiv:`, `github:`, `hf-`, `doi:`) would
  catch HN→artifact references, but it forces an ontology question: an HN Item
  is a *story about* a repo, while the GitHub Item *is* the repo. Dropping either
  corrupts a stream. `dedup_papers` avoids this because both Sources gather the
  same paper.
- Fuzzy headline matching is the only way to catch press↔press, and it is a
  *guess*. The observed signal (0.29) is near noise; the Gemini pair barely
  clears what two unrelated model-release headlines score.
- Prior question, unanswered: for a personal reading queue, is a second account
  of one event wrong? The Brief is "what one reader thought that morning."

If the noise matters, the cheaper lever is **volume, not identity** — a
press-group cap, or a lower `CEILING` for the new Sources — so four press
Sources cannot crowd arXiv/HF out of a 25-Item `EDITION_MAX`. The Decoder alone
contributes up to 8.

## Jev availability, checked 2026-09-21

Still live. `jev.reachable()` → True; `POST /api/v1/systemone` with
`typesafe/jev-1.13` returned HTTP 200, and the response's `model` field was
`typesafe/jev-1.13-20260917` — the dated build behind the pinned alias, which is
what `config.JEV_MODEL` is for. It is **not** in OpenRouter's public `/models`
list (446 entries, none named `jev`/`systemone`), which is expected: that list
does not enumerate the Decisions endpoint.

## Caveats for the next person

- The three new modules duplicate `_text`/`_collapse`/`_parse_time`/`_clean`
  from `wired.py`. That is the convention here (every Source module carries its
  own), not an oversight — but it is four copies now.
- `the_decoder.py`'s docstring says "the one beat none of the existing nine
  covers." Still reads correctly as the nine it joins; it is the tenth.
- MarkTechPost's titles are SEO-shaped and its listicles ("Best Voice Cloning
  APIs in 2026") are a kind of Item the Rubric has never seen. If it is ever
  registered, the Rubric likely needs a line about roundups.
