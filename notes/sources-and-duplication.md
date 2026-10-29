# Candidate Sources and cross-source duplication

Carried over from the handoff that added The Decoder as the tenth Source
(2026-09-21). The facts are as of that date.

`generator/sources/arstechnica.py` and `marktechpost.py` are drafts and
are **not registered**. Registering one means adding it to
`config.SOURCE_ORDER`, `config.SOURCE_LABELS` and `sources.FETCHERS`
(`./check.sh` confirms the three agree), plus the Source count in
`README.md` and `CONTEXT.md`. MarkTechPost's listicles are a kind of
Item the Rubric has never judged; it likely needs a line about roundups.

## Added since: Schneier on Security (2026-10-28)

Registered as the eleventh Source at the reader's request — his choosing
is the point. It reads the whole-blog feed, `schneier.com/feed/`, not
`/tag/ai/feed/`: the tag missed an untagged post about Qwen3-Coder bias.
The cost is off-topic posts (squid, PHP patches) for the Score to drop.
About one post a weekday; ~3 clear the 72h window.

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
