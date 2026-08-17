# Source query research (issue #4)

Research date: 2026-08-17. All curl calls below were run with
`-A "ai-brief-research/1.0 (research)"` against live endpoints on this date. Raw
response snippets are quoted inline as evidence. "Docs say" = a claim taken from
official documentation with a citation URL. "Observed" = a claim I only verified
empirically, marked **undocumented — determined empirically** where no official
doc says it.

---

## 1. arXiv

### `search_query` syntax for the 5-category OR

Docs: the `search_query` field grammar is described at
https://info.arxiv.org/help/api/user-manual.html#query_details — categories are
matched with `cat:` and boolean terms are joined with `+AND+`, `+OR+`, `+ANDNOT+`.

Verified query:

```
https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:stat.ML&start=0&max_results=5&sortBy=submittedDate&sortOrder=descending
```

Observed category tags on the 5 returned entries:

```
2 cs.AI
4 cs.CV
1 cs.LG
1 stat.ME   <- NOT one of the 5 requested categories
1 stat.ML
```

**Note (observed):** a paper can carry *more* category tags than the one(s) it
matched on — `stat.ME` showed up as a secondary/cross-listed category on an
entry whose primary category was one of the 5 requested. The OR-query matches
on *any* category tag present, so the generator must not assume every returned
paper's categories are a subset of `{cs.AI, cs.LG, cs.CL, cs.CV, stat.ML}` —
it should explicitly re-check the returned `<category>` list if it wants to
filter strictly, or just accept cross-listed papers as in-scope (recommended,
see final section).

### Paging (`start` / `max_results`)

Docs (https://info.arxiv.org/help/api/user-manual.html#paging):
- `start`: 0-based index of first result, default `0`.
- `max_results`: number of results to return, default `10`.
- "the maximum number of results returned from a single call (`max_results`) is
  limited to 30000 in slices of at most 2000 at a time."
- A request with `max_results > 30000` returns HTTP 400.

Verified empirically — `start=0` vs `start=10` (`max_results=3` each) returned
disjoint, correctly-offset id sets:

```
start=0:  2608.14546v1 2608.14543v1 2608.14542v1
start=10: 2608.14502v1 2608.14498v1 2608.14496v1
```

`opensearch:` fields on a live response: `itemsPerPage=3`, `totalResults=594606`,
`startIndex=0` — confirms the OpenSearch pagination envelope described in the
docs.

### `published` vs `updated` — submitted date vs current-revision date

Docs (Atom spec, referenced at
https://info.arxiv.org/help/api/user-manual.html#_entry_data): each `<entry>`
has both `<published>` and `<updated>`. Observed on a fresh (v1, un-revised)
submission, both are identical:

```
id: http://arxiv.org/abs/2608.14546v1
published: 2026-08-14T17:59:01Z
updated:   2026-08-14T17:59:01Z
```

Observed on a revised paper (v3), sorted by `lastUpdatedDate` on `cat:cs.LG`,
`published` (original v1 submission time) and `updated` (latest revision
timestamp) genuinely diverge:

```
http://arxiv.org/abs/2602.11626v3 published=2026-02-12T06:22:59Z updated=2026-08-14T17:52:24Z
http://arxiv.org/abs/2603.01959v2 published=2026-03-02T15:08:14Z updated=2026-08-14T17:28:22Z
http://arxiv.org/abs/1908.00882v6 published=2019-08-02T14:37:29Z updated=2026-08-14T15:20:09Z
```

**Implication for "what's new today":** the generator must filter/sort on
`<published>` (original submission date), not `<updated>` — otherwise a 2019
paper that got a routine v6 typo fix today would look like breaking news. Use
`sortBy=submittedDate` for the daily pull.

### Announcement lag

Docs: https://info.arxiv.org/help/submit/index.html —

> "New submissions received by 14:00 (Eastern Daylight/Standard Time Zone) are
> generally made available at 20:00 (Eastern)."

So:
- Best case: a paper submitted just before the 14:00 ET cutoff appears ~6 hours
  later at 20:00 ET the same day.
- Worst case: a paper submitted at 14:01 ET waits for the *next* business day's
  20:00 ET announcement — up to roughly 30 hours later, and longer over a
  weekend since arXiv does not announce on Saturday/Sunday (confirmed by the
  same submission-schedule page).
- Net: "new in the last 24 hours" by submission timestamp and "new in the last
  24 hours of *announcements*" are different sets. A pull keyed on `published`
  timestamp with a 24h window will sometimes miss papers that were submitted
  in-window but not yet announced, and will include papers that were announced
  today but technically submitted slightly more than 24h ago. Given the daily
  cadence of this generator, this is a small, tolerable skew — but it's real
  and worth documenting rather than assuming submission == announcement.

### Rate limit / politeness delay

Docs, https://info.arxiv.org/help/api/tou.html:

> "When using the legacy APIs (including OAI-PMH, RSS, and the arXiv API), make
> no more than one request every three seconds, and limit requests to a single
> connection at a time."

Docs, https://info.arxiv.org/help/api/user-manual.html:

> "In cases where the API needs to be called multiple times in a row, we
> encourage you to play nice and incorporate a 3 second delay in your code."
>
> "search results do not change until new articles are added. Therefore there
> is no need to call the API more than once in a day for the same query. Please
> cache your results."

**Practical rule for this generator:** one call per category-set query per run
(the 5-category OR can be done in a single call), no need to hammer it; if
paging past `max_results=2000` sleep 3s between calls.

---

## 2. Hacker News (Algolia HN Search API)

### Documented endpoints/params

https://hn.algolia.com/api documents `search` (relevance-ranked) and
`search_by_date` (chronological), with params including `query`, `tags`,
`numericFilters`, `page`, `hitsPerPage`. (The docs page itself is a thin SPA
shell with little prose — most of what's usable is the param reference; no
rate limit is stated there, see below.)

### Points threshold — empirical distribution

Pulled every HN story created in a real 24h UTC window
(2026-08-16T00:00Z–2026-08-17T00:00Z):

```
curl -s -A "$UA" "https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=created_at_i%3E1786838400,created_at_i%3C1786924800&hitsPerPage=1000"
```

`nbHits = 734` (all 734 returned in one page since `hitsPerPage=1000` > total).

Points percentiles over all 734 stories from that window:

| percentile | points |
|---|---|
| p50 | 2 |
| p75 | 4 |
| p90 | 14 |
| p95 | 51 |
| p99 | 306 |
| max | 637 |

Counts above thresholds:

| threshold | count (of 734) |
|---|---|
| points ≥ 20 | 62 |
| points ≥ 50 | 37 |
| points ≥ 100 | 24 |

**Undocumented — determined empirically:** there is no official "good
threshold," this is purely observed for one day. Given the project's 15-25
items/day *total* target across 5 sources, HN's share should be roughly
3-6 items/day. `points > 50` yields ~37/day at this specific 24h sample,
which is still too many to include wholesale; `points > 100` yields ~24/day,
close to the whole day's total budget by itself. A workable starting
threshold is **`points > 75`** as a first filter, then rank by points within
the pull and take the top handful (rather than hard-coding a fixed points
cutoff), since HN's daily volume/quality varies.

### Show HN / Ask HN

Tested `tags=show_hn` and `tags=ask_hn` directly — both work and return
results scoped to that story type:

```
tags=show_hn, same 24h window: nbHits=106, e.g. "Show HN: A visual ping utility..."
tags=ask_hn,  same 24h window: nbHits=22,  e.g. "Ask HN: Claude Seems Down"
```

**Observed:** Show HN / Ask HN stories are *also* returned by a plain
`tags=story` pull (no special tag needed) — they simply carry an additional
`_tags` entry. Example from the `tags=story` pull above:

```json
"title": "Show HN: A visual ping utility that is pretty",
"_tags": ["story", "author__ache_", "story_49325004", "show_hn"]
```

So no special query is required to include them; they just need to clear
whatever points threshold is chosen like any other story. Given they skew
lower-points/more numerous (106 Show HN posts in one day vs. only 24
stories total clearing 100 points), they will rarely clear a threshold like
`points > 75` on their own merits, which is a reasonable outcome for an
AI-focused daily brief.

### Rate limit

**Undocumented — could not find a published number.** Checked
https://hn.algolia.com/api (thin SPA, no rate-limit text found — grepped the
raw HTML, no "rate" or "limit" string present) and
https://github.com/algolia/hn-search (archived repo, Rails app source, no
public API rate-limit doc). Response headers on 5 rapid successive requests
showed only `x-cloud-trace-context` (GCP tracing), no `X-RateLimit-*` or
`Retry-After` headers. Treat this as a free community service with no
published SLA or limit — be conservative (one pull per run, cache the day's
result) rather than relying on an unstated ceiling.

---

## 3. Hugging Face

### What `trendingScore` measures

**Undocumented — could not find a definition of the underlying formula or
window.** Checked:
- https://huggingface.co/docs/hub/api — this page has been superseded by an
  OpenAPI spec; contains no description of `trendingScore`.
- The live OpenAPI spec/reference (https://huggingface.co/.well-known/openapi.md,
  fetched directly) lists `trendingScore` only as one of the valid `sort`
  enum values for `/api/models` (`downloads | likes | lastModified |
  trendingScore | likes30d | _id | id`) — no schema-level description of what
  it computes or over what window.
- https://discuss.huggingface.co search for "trendingScore" surfaced no
  forum threads with a staff explanation.

Conclusion: `trendingScore` is a real, working sort key (confirmed via live
query, see below) but its formula and time window are **not publicly
documented anywhere I could find**. Treat it as a black-box "what's hot right
now" ranking, useful for eyeballing but not something to reason precisely
about (e.g. don't assume it's a strict function of last-24h downloads).

### Does `/api/datasets` support `sort=trendingScore`?

Yes — confirmed empirically and via the OpenAPI param table (which lists the
same sort enum for datasets). Live query:

```
curl -s "https://huggingface.co/api/datasets?sort=trendingScore&direction=-1&limit=3"
-> HTTP 200
-> top result: HuggingFaceFW/fineweb, trendingScore=68, likes=3223, downloads=401921
```

### `/api/daily_papers` field list

Live query: `curl -s "https://huggingface.co/api/daily_papers?limit=2"`. Top-level
keys per item, and nested `paper` object keys, observed on a real response:

Top level: `paper`, `publishedAt`, `title`, `summary`, `mediaUrls`,
`thumbnail`, `numComments`, `submittedBy`, `organization`.

`paper` sub-object: `id` (arXiv id, e.g. `"2608.13545"`), `authors[]`,
`mediaUrls[]`, `publishedAt`, `submittedOnDailyAt`, `title`,
`submittedOnDailyBy`, `summary`, `upvotes`, `discussionId`, `projectPage`,
`ai_summary`, `ai_keywords[]`, `ai_summary_model`, `organization`.

Note the duplication: top-level `title`/`summary`/`publishedAt` largely mirror
`paper.title`/`paper.summary`/`paper.publishedAt`, but `paper.id` (the arXiv
id) only lives inside the nested `paper` object.

### Where the arXiv id lives (for dedup)

- **`/api/daily_papers`**: `item.paper.id`, a bare arXiv id string with no
  `arxiv:` prefix and no version suffix, e.g. `"2608.13545"`.
- **`/api/models`**: inside the `tags` array as a prefixed string, e.g.
  `"arxiv:2504.13181"`. Observed on live models (from a `trendingScore` pull):

```
meta-models/Muse-Glimmer-30B         ['arxiv:2504.13181', 'arxiv:2602.06036']
Lightricks/LTX-2.5                   ['arxiv:2601.03233']
deepseek-ai/DeepSeek-V4-Pro-0813      ['arxiv:2606.19348']
```

  A model can cite more than one arXiv id (multiple tags). Strip the
  `arxiv:` prefix to compare against `daily_papers`' `paper.id` for dedup.
  Also useful: the documented `arxivIds` query param on `/api/models` (from
  the OpenAPI spec) — `Filter by Arxiv ID` — could be used directly to check
  "has this arXiv paper already produced a trending model" instead of
  scanning tags client-side.

### Rate limits (bonus — asked implicitly by "does ToS forbid this")

Docs: https://huggingface.co/docs/hub/rate-limits — anonymous (unauthenticated,
per-IP) requests to the "Hub APIs" bucket (which includes `/api/models`,
`/api/datasets`, `/api/daily_papers`) are capped at **500 requests per 5-minute
window**; this generator's daily handful of calls is trivially inside that.

---

## 4. dev.to

### Tags worth pulling

Live `per_page=100` counts on 2026-08-17 (a rough proxy for tag activity/depth,
not filtered to 24h):

```
tag=ai                    -> 100 (capped at per_page)
tag=machinelearning       -> 100 (capped at per_page)
tag=llm                   -> 100 (capped at per_page)
tag=chatgpt               -> 100 (capped at per_page)
tag=artificialintelligence -> 9   (small — low-volume tag)
```

`ai`, `machinelearning`, `llm`, and `chatgpt` all clearly have deep-enough
recent activity to fill 100 results; `artificialintelligence` is thin and can
be dropped or kept only as an extra dedup source. Recommendation: pull `ai`
and `llm` at minimum, `machinelearning` and `chatgpt` if broader coverage is
wanted, then dedup by article `id`/`url` across tags (a single article can
carry multiple of these tags).

### `per_page` / `page` behavior

Docs: https://developers.forem.com/api (interactive reference at
`/api/v1#tag/articles/operation/getArticles`) —

> `per_page` — default **30**, allowed range **[1..1000]** (overridable server-side
> via `API_PER_PAGE_MAX`).
> `page` — "Pagination page", default 1, minimum 1.

Verified empirically: `per_page=1000&tag=ai` returned exactly 1000 items with
HTTP 200 (no truncation, no error) — confirms the doc's stated ceiling is
real and generous.

Paging with `page=1` vs `page=2` (`per_page=5`) returned disjoint id sets, but
the ids were **not monotonically related to published order** — see next
point.

### Is `published_at` reliable, and what timezone?

Format observed on real articles: `"2026-08-15T13:06:49Z"` — ISO-8601, **UTC**
("Z" suffix), consistently present alongside a duplicate
`published_timestamp` field with the same value.

**Important, undocumented-by-example finding:** the default `/api/articles`
listing for a tag is **not sorted by `published_at` descending**. Pulling
`per_page=1000&tag=ai` and checking:

```
min published_at = 2026-08-13T14:24:17Z
max published_at = 2026-08-17T07:35:35Z
sorted descending by published_at? False
```

i.e. the default order mixes recency with (presumably) a relevance/engagement
signal, not pure chronology. **Implication:** the generator cannot assume the
first N results of a plain tag pull are the newest N articles — it must pull
a generously large `per_page` (e.g. 1000, confirmed safe above) and then
filter/sort client-side on `published_at` within the 24h window, rather than
relying on API-side ordering or stopping early once results "look old."

### Rate limit

**Undocumented — could not find a published number.** Checked
https://developers.forem.com/api directly; the page states docs "may be out
of date" and directs rate-limit questions to `yo@forem.com`. No
`X-RateLimit-*` response headers were observed on live requests either. Same
practical guidance as HN: pull once per day, don't hammer it.

---

## 5. GitHub Trending (HTML scrape)

No official API exists. Confirmed unofficial mirror `api.gitterapp.com` 404s
(established in earlier charting work). Live fetch used for selector
verification:

```
curl -s -A "$UA" "https://github.com/trending?since=daily"  -> HTTP 200, 538,567 bytes
```

### CSS selectors (verified against the real HTML fetched above)

- **Row container**: `article.Box-row` — 7 matches on this day's page (one per
  trending repo shown).
- **Repo name**: `h2.h3.lh-condensed > a` — `href` attribute is the
  `/owner/repo` path; visible text is split across a muted "owner /" span and
  the repo name, e.g.:

```html
<h2 class="h3 lh-condensed">
  <a ... href="/cordiverse/cordis" class="Link">
    <svg .../>
    <span class="text-normal">cordiverse /</span>
    cordis</a>
</h2>
```

  → parse `href` for the canonical `owner/repo`, or strip/join the
  `span.text-normal` text with the trailing text node.

- **Description**: `p.col-9.color-fg-muted.my-1` (full class attr in the
  wild is `"col-9 color-fg-muted my-1 tmp-pr-4"`; match on `col-9` +
  `color-fg-muted` since GitHub appends utility classes like `tmp-pr-4` that
  look internal/unstable):

```html
<p class="col-9 color-fg-muted my-1 tmp-pr-4">
  Meta-Framework of Spatiotemporal Composability
</p>
```

- **Language**: `span[itemprop="programmingLanguage"]` — 7 matches, one per
  row, e.g. `<span itemprop="programmingLanguage">TypeScript</span>`. Rows
  with no detected language simply omit this element — the parser must
  handle a missing language gracefully.

- **Total stars**: first `a[href$="/stargazers"]` within the row —
  `<a href="/cordiverse/cordis/stargazers" ...>5,183</a>` (comma-formatted
  text, needs `int(text.replace(',', ''))`).

- **Stars-today delta**: `span.float-sm-right` (full class
  `"d-inline-block float-sm-right"`) at the end of the row — text is
  `"720 stars today"`; needs a regex like `(\d[\d,]*) stars today` since the
  number and the label share one text node with an `<svg>` icon in between.

### Fragility

This is a scrape with **no SLA whatsoever**. GitHub is known to change
trending-page markup periodically (utility class churn is already visible —
classes like `tmp-mr-3`, `tmp-pr-4`, `tmp-ml-0` look like in-flight CSS
migration artifacts that could be renamed/removed without notice). Every
selector above should be treated as "correct as of 2026-08-17" and the
generator should fail soft (skip GitHub Trending for the day, log a warning)
rather than crash if the row count comes back as 0 or expected elements are
missing — this is the single most fragile of the five sources.

### Narrowing to AI-adjacent content

- `?spoken_language_code=en` → HTTP 200, works as an additional query param
  (narrows by *README's* detected human language, not repo topic — not
  directly useful for AI-topic filtering, but harmless to combine).
- `/trending/<language>` (tested `/trending/python?since=daily`) → HTTP 200,
  works, lets you scope to a single programming language (e.g.
  `/trending/python`, `/trending/jupyter-notebook`) — useful as a *secondary*
  pull alongside the unscoped daily page, since a lot of AI repos are
  Python/Jupyter, but this is a heuristic, not a topic filter, and will also
  surface non-AI Python repos.
- `/topics/artificial-intelligence` → HTTP 200, real content (59
  topic/repo-card style matches in the raw HTML), **but it has no `since=daily`
  equivalent** — no "sort by trending today" option was found on this URL; it
  appears to rank by stars/relevance rather than recent trending activity, so
  it doesn't solve the "new in the last 24h" problem and is not a good primary
  source, only a possible cross-reference/dedup aid.

---

## 6. Terms of Service / robots.txt

### arXiv

- `https://arxiv.org/robots.txt` (the main web host, not the API host):
  `User-agent: *`, `Crawl-delay: 15`, explicitly `Allow:`s `/abs`, `/pdf`,
  `/html`, `/list`, etc. — this is for the human-facing website.
- `https://export.arxiv.org/robots.txt` (the host the API actually lives on):

```
User-agent: *
Disallow: /
```

  **This is a blanket disallow of the entire `export.arxiv.org` host for
  generic crawlers.** However, arXiv's own official API documentation
  (https://info.arxiv.org/help/api/user-manual.html,
  https://info.arxiv.org/help/api/tou.html) explicitly directs API consumers
  to use `http(s)://export.arxiv.org/api/query` and spells out separate,
  API-specific access terms (the 3-second delay quoted in section 1) rather
  than referencing the general robots.txt crawl rules. The ToU page
  (checked directly) does not explicitly reconcile this tension — it never
  mentions robots.txt at all. **My read (not an authoritative legal
  conclusion): the blanket `Disallow: /` on `export.arxiv.org/robots.txt` is
  aimed at generic web crawlers hitting that host, while arXiv's own docs
  affirmatively invite programmatic API use of that same host under the
  3-second-delay rule** — but this is a genuine inconsistency in arXiv's own
  published rules, not something I can wave away. If being conservative
  matters, it's worth an email to arXiv's support (a path they explicitly
  invite in the ToU for higher-frequency use) to confirm, though for a
  once-daily, few-requests pull respecting the 3s delay this is very unlikely
  to draw any attention.
- No clause found in the ToU prohibiting a once-daily automated metadata pull
  at this volume; the ToU's main restrictions are about *not* mirroring
  full-text/e-print content and not exceeding the request-rate guidance.

### Hacker News / Algolia

- We are calling `hn.algolia.com`, **not** `news.ycombinator.com` directly —
  `news.ycombinator.com/robots.txt` (`Crawl-delay: 30`, disallows a list of
  action endpoints like `/vote?`, `/reply?`) does not apply to Algolia's
  separate search service/host.
- `hn.algolia.com/robots.txt` → HTTP 404 (no robots.txt published at all on
  that host).
- No terms-of-service document specific to the HN Search API was found (the
  main Algolia docs page for it 404s at the URL given in the ticket; the
  archived `algolia/hn-search` GitHub repo has no ToS). **No clause found
  prohibiting this use** — but also no explicit permission; it's offered as a
  free public service with no published usage terms either way.

### Hugging Face

- `https://huggingface.co/robots.txt`:

```
User-agent: *
Allow: /
```

  Open to all crawlers, no disallows, ships a sitemap.
- Rate limits are documented (see section 3) but are a technical throttle, not
  a legal prohibition — a once-daily handful of `/api/models`,
  `/api/datasets`, `/api/daily_papers` calls is trivially within the 500
  req/5-min anonymous cap. **No clause found prohibiting this use.**

### dev.to

- `https://dev.to/robots.txt`: `User-agent: *` with a list of specific
  `Disallow:`s (admin/mod panels, search, auth callbacks, abuse reports) —
  **`/api/articles` is not in the disallow list**, and API usage isn't
  addressed by robots.txt at all (robots.txt governs the HTML site, the API is
  a separate concern per Forem's own docs).
- `https://dev.to/terms` was checked directly — **no clause found** addressing
  scraping, bots, or automated/API access at all; the terms are silent on
  this. Forem's public developer docs (https://developers.forem.com/api)
  present the API as intended for third-party programmatic use with no
  additional legal restriction stated.

### GitHub

- `https://github.com/robots.txt`, `User-agent: *` section, includes:

```
Disallow: /*since=*
```

  **This is a direct, literal match against the exact URL this project is
  planning to scrape**: `https://github.com/trending?since=daily` contains
  the substring `since=`, so it falls under this `Disallow` rule for generic
  crawlers (`User-agent: *`). This is worth flagging clearly: **a
  robots.txt-respecting fetch of `github.com/trending?since=daily` is
  disallowed.** (For contrast, `/trending/python?since=daily` and
  `/topics/artificial-intelligence` are also affected by the same
  `since=` wildcard pattern whenever a `since=` query string is present;
  `/topics/artificial-intelligence` with no query string is not.)
- GitHub's Acceptable Use Policies
  (https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)
  define scraping ("extracting information from our Service via an automated
  process, such as a bot or webcrawler") and permit it for legitimate
  research/archival purposes, but separately prohibit "excessive automated
  bulk activity" under their spam/inauthentic-activity section. A once-daily
  single-page fetch is not remotely "excessive," but the **robots.txt
  `since=` disallow is a concrete, citable conflict** that a strictly
  robots.txt-respecting scraper should not ignore. This is the single
  clearest ToS/robots concern found across all five sources.

---

## What this means for the generator

**arXiv**
- Query: `search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:stat.ML&sortBy=submittedDate&sortOrder=descending&start=0&max_results=100`
  (100 is plenty of headroom for a 24h window; increase in slices of 2000 only
  if truly needed).
- Filter by `<published>`, not `<updated>`, for "new today."
- Always send a `User-Agent` header (already established) and a real contact
  string per the ToU's spirit.
- Respect the 3-second delay if you page at all; for a single ≤100-result call
  once a day this is essentially moot.
- Be aware announcement lag can push a paper's visible "new" date up to ~30h
  after submission (or longer over a weekend) — don't be surprised by
  apparent gaps on Mondays or after US holidays.
- Note the `export.arxiv.org/robots.txt` full-disallow vs. the API docs'
  explicit invitation to use that host — documented above, not fully
  resolved; low practical risk at this volume.

**Hacker News**
- `tags=story&numericFilters=created_at_i>{start},created_at_i<{end}` for a
  UTC 24h window is sufficient; Show HN / Ask HN are included automatically,
  no extra tag needed.
- Start with `points > 75` as a floor, then take the top ~5 by points (not a
  hard cutoff) to keep HN's share of the 15-25 item budget around 3-6 items;
  re-tune after watching a few real days, since the percentile table above is
  a single-day sample.
- No known rate limit — one pull per run is safe regardless.

**Hugging Face**
- Use `/api/models?sort=trendingScore&direction=-1&limit=~20` and
  `/api/datasets?sort=trendingScore&direction=-1&limit=~20` (confirmed both
  work); treat `trendingScore` as an opaque "hot now" signal, not something
  to explain to readers in a precise way since HF doesn't document its
  formula.
- Pull `/api/daily_papers?limit=~20` for the papers feed.
- Dedup key across models/daily_papers/arXiv: strip the `arxiv:` prefix from
  `/api/models` tags and compare against `paper.id` from `/api/daily_papers`
  and the numeric arXiv id from the arXiv Atom `<id>`. Optionally use the
  `arxivIds` query param on `/api/models` directly instead of scanning tags.
- Comfortably inside the 500 req/5-min anonymous rate limit at this volume.

**dev.to**
- Pull `tag=ai` and `tag=llm` at minimum (both have deep recent volume);
  `machinelearning`/`chatgpt` optional for broader coverage;
  `artificialintelligence` alone is too thin to bother with.
- Use a large `per_page` (500-1000, confirmed to work up to 1000) since
  default ordering is **not** chronological — sort/filter client-side on
  `published_at` (UTC, ISO-8601 `Z` format) for the 24h window rather than
  trusting API order or paging until results "look old."
- Dedup by article `id` across tags (an article can carry more than one
  pulled tag).
- No known rate limit; pull once per run.

**GitHub Trending**
- Scrape `github.com/trending?since=daily` with the selectors documented
  above (`article.Box-row` rows; `h2.h3.lh-condensed > a` for name;
  `p.col-9.color-fg-muted` for description;
  `span[itemprop="programmingLanguage"]` for language; first
  `a[href$="/stargazers"]` for total stars; `span.float-sm-right` regex
  `(\d[\d,]*) stars today` for the delta).
- **Flag explicitly to the maintainer**: this exact URL is disallowed by
  `github.com/robots.txt` (`Disallow: /*since=*`) for generic crawlers. A
  once-daily, single-page, low-volume pull is very unlikely to draw
  enforcement action and is arguably covered by GitHub's "legitimate
  research" carve-out in the Acceptable Use Policy, but it is not
  robots.txt-clean, and this is the one source in the set where a strict
  reading says don't. Decide consciously whether to proceed, and if so, wrap
  the parser defensively (fail soft / skip the day, don't crash) since GitHub
  markup can and does change without notice.
- Consider `/trending/python` and `/trending/jupyter-notebook` as
  supplementary pulls for AI-adjacent repos (heuristic, not a topic filter);
  `/topics/artificial-intelligence` is not date-scoped and isn't a good "new
  today" source, only a possible cross-check.

**Volume target (15-25 items/day) — worked recommendation**

| source | suggested daily take | rationale |
|---|---|---|
| arXiv | 5-8 | 5 categories, huge daily volume — score/rank with the local model and take the top handful |
| Hacker News | 3-5 | `points > 75` floor, take top ~5 by points |
| Hugging Face (models+datasets+papers combined) | 4-6 | trendingScore top few from each of 3 endpoints, dedup by arXiv id |
| dev.to | 2-4 | filter to last 24h by `published_at`, rank by `public_reactions_count` |
| GitHub Trending | 1-3 | top few "stars today" rows, contingent on the robots.txt decision above |
| **total** | **15-26** | matches the 15-25 target; the local Ollama model's scoring step is what actually trims each source's raw pull down to this range, these are per-source *ceilings* to pull before scoring, not fixed output counts |

**Timezone handling**: standardize everything to UTC internally. arXiv
timestamps are UTC `Z`, dev.to `published_at` is UTC `Z`, HN's
`created_at_i` is a Unix epoch (UTC by definition) — only GitHub Trending's
"stars today" has no explicit timestamp/timezone at all (it's GitHub's own
rolling "daily" window, opaque to us), so treat it as "as of when we
fetched it" rather than a precise 24h-UTC window like the other four.
