# Getting structured scores out of `gemma4:e4b` (ai-brief issue #5)

Research date: 2026-08-17. Machine: local dev box, Ollama reachable at
`http://localhost:11434` (WSL2, Ollama running on the Windows host and
port-forwarded into WSL — no local `ollama` CLI or systemd unit visible from
this shell, which is why some answers below are drawn from `curl` + docs
rather than `ollama ps` / `systemctl show`).

Model under test: `gemma4:e4b`, 8.0B params, Q4_K_M, capabilities
`["completion", "vision", "audio", "tools", "thinking"]` (per `/api/show`),
context length **131072** tokens (`gemma4.context_length` in `/api/show`
`model_info`).

Everything below is labeled **DOCUMENTED** (cited URL) or **EMPIRICAL**
(command + raw response included). Raw request/response JSON files used to
produce this report are also in the scratch working directory used during
research and are reproduced inline here; anything not inlined can be
regenerated with `research/score_item.py` or the `curl` commands shown.

---

## 1. Does `format` (JSON-schema structured output) work with `gemma4:e4b`?

**EMPIRICAL (tested 2026-08-17): yes.**

Request (`/api/chat`):

```json
{
  "model": "gemma4:e4b",
  "messages": [
    {"role": "system", "content": "You are an item scorer for an AI news brief. Score how interesting/important the item is to an AI practitioner audience on a 1-5 scale (5=must-see) and write a one-sentence synopsis."},
    {"role": "user", "content": "Title: Attention Is All You Need\nAbstract: The dominant sequence transduction models are based on complex recurrent or convolutional neural networks in an encoder-decoder configuration. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely."}
  ],
  "format": {"type":"object","properties":{"score":{"type":"integer","minimum":1,"maximum":5},"synopsis":{"type":"string"}},"required":["score","synopsis"]},
  "stream": false
}
```

Response (thinking still enabled here — see §2):

```json
{
  "model": "gemma4:e4b",
  "created_at": "2026-08-17T07:36:43.6498401Z",
  "message": {
    "role": "assistant",
    "content": "{\n  \"score\": 5,\n  \"synopsis\": \"This landmark paper introduced the Transformer architecture, proving that solely attention mechanisms can replace traditional recurrent and convolutional structures for sequence transduction.\"\n}",
    "thinking": "Here's a thinking process for scoring this item:\n\n1.  **Analyze the Audience:** ... (full chain-of-thought, ~250 words) ..."
  },
  "done": true,
  "done_reason": "stop",
  "total_duration": 12896460400,
  "load_duration": 6052326200,
  "prompt_eval_count": 490,
  "prompt_eval_duration": 158852000,
  "eval_count": 43,
  "eval_duration": 689168000
}
```

`message.content` is valid, schema-conformant JSON on every one of the ~30
calls made during this research (10 sequential + 14 concurrent + 10
sequential quality-check items, all with `format` set). No non-JSON content
was observed when `format` was supplied. Ollama uses constrained decoding
(GBNF-style grammar) to guarantee syntactic conformance to the schema, so
**malformed JSON only happens if generation is cut off before the object
closes** — see the truncation test in §6.

An invalid `format` value is rejected outright with HTTP 500 (§6).

## 2. Does structured output compose with thinking, or conflict? Can thinking be disabled?

**DOCUMENTED (source: https://ollama.com/blog/thinking , https://docs.ollama.com/api/chat ):**
Ollama exposes a `think` request field. Per the API docs: *"Format to
return a response in. Can be `json` or a JSON schema"* for `format`, and for
`think`: it accepts booleans (`true`/`false`) or, on models that support
graded effort, the strings `"low"`/`"medium"`/`"high"`/`"max"`. When
thinking is enabled, *"the model will return a separate thinking output in
addition to content"* — the reasoning goes into a **separate response field
named `thinking`** on the message object; `message.content` holds only the
final answer. Setting `"think": false` makes the model "not think and
directly output the content."

**EMPIRICAL (tested 2026-08-17): they compose, and disabling thinking works
and is drastically cheaper.**

With `think` omitted (defaults on for a `thinking`-capable model), the
reasoning appeared verbatim in `message.thinking`, and `message.content` was
still clean, schema-valid JSON (see §1 response above) — so yes, `format`
and thinking **compose without conflict**, and the reasoning never leaked
into `content`.

With `"think": false` added to the same request:

```json
{
  "model": "gemma4:e4b",
  "created_at": "2026-08-17T07:37:12.554033Z",
  "message": {
    "role": "assistant",
    "content": "{\n\"score\": 5,\n\"synopsis\": \"This seminal paper introduced the Transformer architecture, which revolutionized sequence modeling by relying entirely on attention mechanisms instead of recurrence or convolutions.\"\n}"
  },
  "done": true,
  "done_reason": "stop",
  "total_duration": 1331533000,
  "load_duration": 400070400,
  "prompt_eval_count": 115,
  "prompt_eval_duration": 284298000,
  "eval_count": 41,
  "eval_duration": 625979000
}
```

No `thinking` key is present at all when `think: false`. Wall time dropped
from ~7.0s (warm, thinking on) to ~1.3s (warm, thinking off) for the
identical prompt — a >5x speedup. `prompt_eval_count` also dropped from 466
to 115 tokens, because Gemma's chat template injects extra thinking-mode
scaffolding into the prompt when thinking is enabled.

**Important latency finding:** with thinking *on*, `eval_duration` +
`prompt_eval_duration` + `load_duration` only summed to ~1.3-6.9s of the
7.0-12.9s `total_duration` observed — several seconds are unaccounted for in
the per-phase fields. The most likely explanation is that the reported
`eval_count`/`eval_duration` undercounts hidden reasoning-token generation
time in this Ollama build. **Practical takeaway: don't trust
`eval_duration` alone to budget thinking-mode latency — measure wall clock.**
This is moot for the recommended design (`think: false`), which has no
such discrepancy.

**Recommendation: always send `"think": false`.** It is compatible with
`format`, produces clean JSON directly in `content` with no parsing of a
separate field required, and is the dominant factor in throughput (§4).

## 3. `/api/chat` vs `/api/generate` — which is right?

**EMPIRICAL (tested 2026-08-17): both work interchangeably for this task;
recommend `/api/chat`.**

`/api/generate` with the same schema and `think: false`:

```json
{
  "model": "gemma4:e4b",
  "response": "{\n  \"score\": 5,\n  \"synopsis\": \"This seminal paper introduced the Transformer architecture, proving that attention mechanisms alone can replace complex recurrent and convolutional layers in sequence modeling.\"\n}",
  "done": true,
  "done_reason": "stop",
  "context": [2, 105, 2364, "... 140 more ints ..."],
  "total_duration": 1577624300,
  "load_duration": 461631400,
  "prompt_eval_count": 111,
  "prompt_eval_duration": 442191000,
  "eval_count": 43,
  "eval_duration": 659799000
}
```

Timing (~1.58s) and output quality were equivalent to `/api/chat` (~1.34s)
for the same input. Functional differences:

- `/api/generate` returns a raw token-id `context` array meant for chaining
  follow-up completions in the *same* conversation. Scoring is a one-shot,
  stateless call per item — this field is dead weight here.
- `/api/chat` gives a clean `system`/`user` role split, which is the more
  natural fit for "here is a fixed system instruction, here is one item's
  title+abstract" and matches how `format` + `think` are documented
  (https://docs.ollama.com/api/chat).
- `/api/generate` also supports `format`/`think` (**DOCUMENTED**, source:
  https://ollama.com/blog/thinking — shows a `/api/generate`-style example
  with `think`) but the structured-outputs blog post
  (https://ollama.com/blog/structured-outputs) only documents `/api/chat`
  explicitly.

**Recommendation: `/api/chat`**, one system message + one user message per
item, no conversation history retained between items (each item is scored
independently per the ticket).

## 4. Throughput — EMPIRICAL (tested 2026-08-17)

All numbers below use `think: false`, `format` = the score/synopsis schema,
model already warm (loaded) unless noted "cold."

### Per-item latency, sequential, 10 real items

Items: a real arXiv abstract (Attention Is All You Need, fetched live from
`export.arxiv.org`), 4 more real arXiv abstracts from `cs.AI` fetched live
(sorted by submission date, 2026-08-17), and 5 real HN front-page stories
fetched live from the HN Firebase API (`topstories.json` + `item/<id>.json`),
including titles, scores, and URLs as of research time.

```
 1.37s  score=5  Attention Is All You Need
 1.18s  score=2  Decoding the Past: An Uncertainty-Aware Deep Learning Framew...
 1.19s  score=5  Marionette: Predicting World States, Rendering Geometry...
 1.13s  score=4  Handover of In-Context Learning State Across Session Boundar...
 1.08s  score=5  Participatory Moral AI Is Not Neutral...
 1.18s  score=3  Learning-to-Transition for Large-scale and High-Order MIMO...
 1.47s  score=4  Qwen 3.8 27B is excellent, but it defaults to overthinking...  (HN, 362 pts)
 1.19s  score=4  Linear Algebra Done Right - Sheldon Axler                     (HN, 34 pts)
 1.21s  score=2  The Life and Death of Direct File [pdf]                      (HN, 180 pts)
 1.30s  score=4  A third world engineer responds to "RISC-V..."               (HN, 473 pts)

TOTAL sequential wall time for 10 items: 12.31s (1.23s/item avg)
```

### Extrapolation (single request at a time, model warm)

- **100-item day:** 10 × 12.31s ≈ **123s (~2 minutes)**
- **300-item day:** 30 × 12.31s ≈ **369s (~6 minutes)**

Both are trivially inside a "runs once daily" batch job budget even fully
sequential. Cold start (model not yet loaded) adds a one-time ~6-12s
penalty (§ below), negligible against either total.

### Concurrency: does it help?

`OLLAMA_NUM_PARALLEL` is **DOCUMENTED** (source: https://docs.ollama.com/faq)
default **1** request processed at a time per loaded model
(`OLLAMA_MAX_LOADED_MODELS` defaults to 3× GPU count, or 3 for CPU). This
instance's actual runtime env var was not directly observable from this
shell (Ollama runs on the Windows host of this WSL2 box; no local
`ollama`/`systemctl` process to introspect — `ollama ps`, `systemctl show
ollama`, and `ps aux | grep ollama` all came back empty/not-found in this
shell). Per-request `keep_alive` was used instead, which does not require
touching global config (constraint honored — no `OLLAMA_NUM_PARALLEL` was
set anywhere).

Measured with a small Python/`concurrent.futures.ThreadPoolExecutor` script
(`research/score_item.py`'s test harness, see scratch `bench.py`),
n concurrent in-flight requests, model warm:

| concurrency n | wall time for n items | effective s/item | per-item latency range |
|---|---|---|---|
| 1 (sequential baseline) | 12.31s / 10 items | 1.23s | 1.08 - 1.47s |
| 2 | 2.12s / 2 items | 1.06s | 1.47, 2.12s |
| 4 | 3.78s / 4 items | 0.95s | 1.37 - 3.78s |
| 8 | 6.93s / 8 items | 0.87s | 1.43 - 6.92s |

Concurrency gives a **modest** win (1.23s → ~0.87-1.06s effective per item)
but per-item tail latency grows a lot (up to 6.9s at n=8) — consistent with
the documented default of `OLLAMA_NUM_PARALLEL=1`: requests are effectively
queued and served close to one-at-a-time by the model runner, so most of
the "concurrency" gain is just amortizing fixed per-request overhead
(connection setup, JSON parse) rather than true parallel GPU decode.

**Recommendation: don't bother with concurrency.** At ~1.2s/item
sequential, a 300-item day finishes in ~6 minutes — well within a daily
batch job's budget — and sequential requests are simpler to reason about
for retry/timeout logic and won't produce the long tail latencies seen at
n=8. If the item count grows an order of magnitude in the future,
concurrency of 2-4 is safe to revisit.

### Cold start vs warm (keep_alive)

- **Cold** (model not loaded, first call of the research session, thinking
  on): `total_duration` = 12.90s, of which `load_duration` = **6.05s**.
- **Warm** (model already resident, second call, thinking on):
  `total_duration` = 7.04s, `load_duration` = **0.41s**.
- **Warm** (thinking off): `total_duration` = 1.33s, `load_duration` = 0.40s.

`keep_alive` (default 5 minutes per **DOCUMENTED**,
https://docs.ollama.com/faq) was set explicitly to `"5m"` in
`research/score_item.py` requests, which is enough to keep the model
resident across a same-run batch of items without ever needing to touch
global Ollama config. First item of a run eats a one-time ~6s load penalty;
every item after that is warm.

## 5. Quality sanity check — EMPIRICAL (tested 2026-08-17), 10 real items

Same 10 items as §4, scores from the `think:false` structured-output calls:

| score | title | sane? |
|---|---|---|
| 5 | Attention Is All You Need (arXiv) | yes — foundational ML paper |
| 2 | Uncertainty-aware sex attribution in prehistoric hand stencils (arXiv) | yes — real but niche/off-topic for an AI-practitioner brief |
| 5 | Marionette: world models for interactive games (arXiv) | yes — squarely on-topic, novel |
| 4 | Handover of in-context learning state across sessions (arXiv) | reasonable — LLM agent infra topic |
| 5 | Participatory Moral AI Is Not Neutral (arXiv) | reasonable — timely AI policy/ethics paper |
| 3 | Learning-to-Transition for MIMO detection (arXiv) | yes — ML-adjacent but telecom-specific, correctly mid-scored |
| 4 | "Qwen 3.8 27B... overthinking" (HN, 362 pts) | yes — directly relevant LLM commentary |
| 4 | Linear Algebra Done Right (HN, 34 pts) | **questionable** — a math textbook link, not AI news; model over-scored it, likely because "linear algebra" pattern-matches as ML-adjacent |
| 2 | The Life and Death of Direct File [pdf] (HN, 180 pts) | yes — correctly identified as off-topic (tax policy) despite decent HN score |
| 4 | RISC-V rebuttal essay (HN, 473 pts) | borderline — correctly picked up general engineering relevance but is hardware/ISA, not AI |

Ordering is largely sane: the two most clearly AI/ML-relevant items scored
highest (5), the two clearly off-topic items scored lowest (2), and
ambiguous/adjacent items landed in the middle (3-4). The one miss is
"Linear Algebra Done Right" scoring a 4 — the model appears to weight
topical keyword overlap ("linear algebra" reads as ML-textbook-adjacent)
over actual newsworthiness to an AI practitioner audience. **This is a
mild finding, not a blocking one**: a single generic system prompt without
few-shot examples or an explicit "is this actually about AI/ML, not just
math-adjacent" instruction will occasionally over-score generically
technical content. If false positives like this show up often in
production, tightening the system prompt (e.g., explicitly stating the
brief's scope: arXiv AI papers, HN/dev.to AI posts, HF/GitHub AI
tooling) or adding 2-3 few-shot examples would likely fix it — no
architecture change needed.

## 6. Failure modes — EMPIRICAL (tested 2026-08-17) + DOCUMENTED (inferred)

| scenario | how tested | result |
|---|---|---|
| Wrong port / daemon unreachable | `curl -m 3 http://localhost:19999/api/chat -d ...` | connection refused; curl returns empty body, `HTTP_STATUS:000`, exits nonzero. **This stands in for "daemon down"** — actually stopping the real Ollama daemon was avoided per constraints; this is the closest safe proxy and is consistent with standard TCP connection-refused behavior on any dead HTTP service. |
| Model not found | `curl -X POST /api/chat -d '{"model":"nonexistent-model:latest",...}'` | `HTTP 404`, body `{"error":"model 'nonexistent-model:latest' not found"}` |
| Malformed request body | `curl -X POST /api/chat -d '{not valid json'` | `HTTP 400`, body `{"error":"invalid character 'n' looking for beginning of object key string"}` |
| Invalid `format` schema | `curl -X POST /api/chat -d '{"format":"not-a-valid-schema-object",...}'` | `HTTP 500`, body `{"error":"invalid format: \"\\\"not-a-valid-schema-object\\\"\"; expected \"json\" or a valid JSON Schema object"}` |
| Truncated/overlong generation | same scoring request but `"options":{"num_predict":3}` to force early cutoff | `HTTP 200` (!), `done:true`, **`done_reason:"length"`**, `message.content = "{\n  "` — syntactically incomplete JSON. **The HTTP layer reports success; only `done_reason` (or a JSON-parse failure on `content`) reveals the truncation.** |
| Refusal | not directly triggered — none of the ~30 items tested (including borderline topics) produced a refusal; gemma4 has no obvious content-policy trigger for AI/tech news scoring | not observed empirically; treat any non-JSON `content` or a schema-violating field (e.g. missing `score`) the same as a parse failure |

**Recommendation for the generator (fail-soft per map note 10):**

1. **Connection-level errors** (refused/timeout/DNS): catch
   `urllib.error.URLError` / equivalent; treat as "Ollama unavailable for
   this run" — skip synopsis generation for *all* items, publish the brief
   with raw titles only. Don't retry per-item in this case (retrying a dead
   daemon 300 times wastes the run's time budget); one connectivity check
   before the item loop starts is enough.
2. **HTTP 4xx (bad request/model not found)**: this is a config/bug, not a
   transient issue — log loudly, but same fallback (raw titles).
3. **HTTP 5xx (bad format schema, server error)**: same as above — these
   should only happen from a code bug in the request builder, not
   per-item data, so don't retry per item; fix the schema.
4. **Truncation / invalid JSON / schema violation (`done_reason != "stop"`,
   or `json.loads` fails, or required fields missing/out of range)**: this
   *is* per-item and worth **one retry** (e.g. with a slightly larger
   `num_predict` / same request again — transient). If the retry also
   fails, fall back to "no synopsis" for that one item only and continue
   the loop — do not abort the whole run.
5. **Timeout**: set a per-request timeout comfortably above the observed
   p99 (~2-7s warm, ~13s cold) — **30s** is a safe generous ceiling used in
   `research/score_item.py`. On timeout, treat like truncation: one retry,
   then fall back to no-synopsis for that item.
6. Check `done_reason` **and** `json.loads(content)` **and** the presence
   of `score` in `[1,5]` and non-empty `synopsis` — don't rely on HTTP 200
   alone as "success," since truncation returns HTTP 200.

## 7. Context limits — EMPIRICAL (tested 2026-08-17) + DOCUMENTED

`gemma4:e4b`'s context window per `/api/show`'s `model_info` is
`"gemma4.context_length": 131072` tokens.

Observed `prompt_eval_count` (tokens consumed by system prompt + one
item's title+abstract) across all test calls ranged from **85 to 490**
tokens (490 was with thinking-mode's extra template scaffolding; 85-115
with `think:false`). Even a long arXiv abstract (a few hundred words) plus
the system prompt stays well under 1,000 tokens per call.

**Conclusion: scoring one item at a time cannot realistically approach the
131,072-token ceiling.** You'd need roughly 100-300x more text per single
item (a full paper's PDF text, not just title+abstract) before context
length becomes a concern. No chunking or truncation strategy is needed for
this use case.

---

## Summary / recommended request shape

```json
POST http://localhost:11434/api/chat
{
  "model": "gemma4:e4b",
  "messages": [
    {"role": "system", "content": "<scoring instructions>"},
    {"role": "user", "content": "Title: ...\nAbstract/Text: ..."}
  ],
  "format": {"type":"object","properties":{"score":{"type":"integer","minimum":1,"maximum":5},"synopsis":{"type":"string"}},"required":["score","synopsis"]},
  "think": false,
  "stream": false,
  "keep_alive": "5m"
}
```

- `format` works and reliably produces valid JSON in `message.content`.
- `think: false` disables thinking cleanly and is ~5x faster than leaving
  it on; when left on, reasoning goes into a separate `message.thinking`
  field and never pollutes `content`.
- `/api/chat`, one system + one user message per item, no history.
- **Throughput: ~1.2s/item sequential, warm → a 300-item day is ~6 minutes
  of Ollama time.** Concurrency saves little given the documented
  `OLLAMA_NUM_PARALLEL=1` default and isn't worth the added tail-latency
  and complexity at this scale.
- Context window (131K tokens) is a total non-issue for single-item
  title+abstract scoring.
- Failure handling: HTTP-level errors (connection refused, 4xx, 5xx) mean
  "skip synopsis generation for the whole run"; per-item truncation/parse
  failures (`done_reason != "stop"` or invalid JSON/schema) mean "retry
  once, then skip synopsis for that one item" — either way the brief still
  publishes with raw titles per map note 10.
