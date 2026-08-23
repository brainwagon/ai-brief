# AI Brief

A daily reading queue for one person. A generator gathers what is new across a
handful of upstreams, a free hosted model scores and summarises it, and the
result is published as a dated page on GitHub Pages.

## Language

### The publication

**Brief**:
The publication as a whole — this repo, and the site it serves. Ongoing and
undated. The thing that has Editions.
_Avoid_: digest, newsletter, report, the blog

**Edition**:
One day's page: dated, published once. Its date is part of its identity,
appearing in the filename, the URL, and the heading as the same string. An
Edition is what a Run produces.

An Edition is not revised to change its judgement — a Score that reads wrong
a week later, a Synopsis that could be better, an Item that turned out to
matter. Those stand: the Brief is a record of what one reader thought that
morning, and a page that keeps improving is no longer that.

It IS revised to repair a Run. When the Edition on the page is not what a
working Run would have produced — every Item Unenriched because the model was
unreachable, a Source Unavailable that was merely slow — the same date may be
Generated again over the top. The repair is deliberate and says so: `--force`
to write over an existing date, today's Snapshots dropped first so the diff is
taken against the previous Edition again, and a commit subject that names the
revision rather than reusing the bare `Edition <date>`.

The line between the two is whether the Edition failed to be *made*, not
whether it turned out to be *good*.
_Avoid_: issue, brief, digest, daily, report, page

**Index**:
The single undated page listing every Edition, and the front door of the Brief.
Undated where an Edition is dated.
_Avoid_: home, archive, landing page, TOC

### The material

**Item**:
One gathered thing — a paper, a story, a repository, a model, a dataset, an
article. The unit an Edition is made of and the unit a Score applies to.
_Avoid_: entry, link, story, article, result, post

**Source**:
One upstream stream of Items, and the unit the per-source ceiling counts
against. There are seven, not five: arXiv, Hacker News, GitHub New Repos,
dev.to, and Hugging Face's models, datasets, and papers separately — Hugging
Face is one site but three Sources.
_Avoid_: feed, provider, upstream, site, GitHub Trending (the name of a page
this project no longer reads — the repositories now come from the search API)

**Identity** (of an Item):
The stable key that says whether two sightings are the same Item, fixed per
Source: the arXiv id with the version stripped (`2508.01234`, never
`2508.01234v2`, so a revision is not new); the Hacker News item id; `owner/repo`
for GitHub New Repos; the repo id `owner/name` for Hugging Face models and
datasets; the arXiv id again for Hugging Face papers; the article id for
dev.to. Hugging Face papers and arXiv share a key form deliberately — that is
what makes their overlap a collision rather than a guess.
_Avoid_: id, key, slug, fingerprint

**Snapshot**:
One Source's recorded set of Identities from one Run. An Item is *new* when its
Identity is absent from the previous Snapshot, which is how Sources that publish
no timestamps are read at all.
_Avoid_: state, cache, seen set, history

**Pick**:
An Item chosen as one of the day's standouts, selected in a second pass over the
high scorers rather than by Score alone.
_Avoid_: highlight, lead, feature, top item

### What the model produces

**Score**:
An Item's interest, 1–5, judged against the Rubric. Assigned per Item and
independently of every other Item.
_Avoid_: rating, rank, grade, weight

**Synopsis**:
The line or two of prose the model writes about an Item, in place of whatever
title the Source supplied.
_Avoid_: summary, description, blurb, abstract

**Rubric**:
The editable statement of what each Score from 1 to 5 means. Deliberately
personal — it encodes one reader's taste and is expected to drift and be
retuned.
_Avoid_: criteria, scoring guide, taste file, weights, heuristics

**Prompt**:
The instructions wrapped around a Rubric to get an Enrichment out of the model.
Separate from the Rubric so that taste can be tuned without touching
model-wrangling.
_Avoid_: template, system message, instructions

### The acts

**Run**:
One execution of the generator. May produce an Edition, and may not.
_Avoid_: job, build, cycle, invocation

**Enrichment**:
The act of putting an Item to the model, producing a Score and a Synopsis. Its
two results are named separately because either can be absent while the other
is not.
_Avoid_: analysis, processing, summarisation

**Generate**:
To write an Edition and update the Snapshots. Touches files only, and never
git — so a failure here is distinguishable from a failure to Publish.
_Avoid_: build, render, compile

**Publish**:
To commit and push. This is what makes an Edition public, Pages serving what it
finds with no build step of its own.
_Avoid_: deploy, ship, release, push live

### When things are missing

**Unavailable** (of a Source):
Failed to answer during a Run, contributing no Items to that Edition and saying
so on the page. A Source-level hole.
_Avoid_: down, failed, errored, missing

**Unenriched** (of an Item):
Present in an Edition with no Score or no Synopsis, because the model could not
be reached or did not answer usefully. Carries its Source's raw title instead.
An Item-level hole.
_Avoid_: raw, unprocessed, degraded, failed
