"""Hugging Face is one site but three Sources: models, datasets and papers.

Models and datasets are trending lists, and `trendingScore` is undocumented —
no published formula, no published window. It is used here only as a sort key,
never as a threshold and never shown to a reader. Novelty for both is the
Snapshot diff: today's top trending datasets were created in 2024 and 2022, so
nothing about the list is new by timestamp.

Papers takes two dates: today's list and yesterday's. The second request covers
the weekend gaps that would otherwise leave the Source silent for days, and
picks up the upvote maturity that the dedup relies on. An empty array from both
dates is a weekend, not an Unavailable Source.
"""

from datetime import timedelta

from ..fetch import get_json, Unavailable
from ..item import Item

MODELS_KEY = "hf-models"
DATASETS_KEY = "hf-datasets"
PAPERS_KEY = "hf-papers"


def fetch_models(run_at):
    body = get_json(
        "https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=30"
    )
    if not isinstance(body, list):
        raise Unavailable("response was not a JSON array")

    seen, items = [], []
    for model in body:
        # `id` is an opaque string: canonical models like `gpt2` have no owner
        # segment, so it is never split on `/`. `_id` is a Mongo id and is not
        # the Identity.
        identity = model.get("id")
        if not identity:
            continue
        seen.append(identity)

        tags = model.get("tags") or []
        downloads = model.get("downloads") or 0
        pipeline = model.get("pipeline_tag")

        text_parts = []
        if pipeline:
            text_parts.append(f"Pipeline: {pipeline}")
        if model.get("library_name"):
            text_parts.append(f"Library: {model['library_name']}")
        readable = [t for t in tags if ":" not in t][:20]
        if readable:
            text_parts.append("Tags: " + ", ".join(readable))

        meta = ["new to trending"]
        if downloads:
            meta.append(f"{downloads:,} downloads")
        if model.get("likes"):
            meta.append(f"{model['likes']:,} likes")

        items.append(
            Item(
                source=MODELS_KEY,
                identity=identity,
                title=identity,
                url=f"https://huggingface.co/{identity}",
                text="\n".join(text_parts),
                meta=" · ".join(meta),
            )
        )
    return items, seen


def fetch_datasets(run_at):
    body = get_json(
        "https://huggingface.co/api/datasets?sort=trendingScore&direction=-1&limit=30"
    )
    if not isinstance(body, list):
        raise Unavailable("response was not a JSON array")

    seen, items = [], []
    for dataset in body:
        identity = dataset.get("id")
        if not identity:
            continue
        seen.append(identity)

        tags = dataset.get("tags") or []
        downloads = dataset.get("downloads") or 0

        text_parts = []
        description = (dataset.get("description") or "").strip()
        if description:
            text_parts.append(description)
        readable = [t for t in tags if ":" not in t][:20]
        if readable:
            text_parts.append("Tags: " + ", ".join(readable))

        meta = ["new to trending"]
        if downloads:
            meta.append(f"{downloads:,} downloads")
        if dataset.get("likes"):
            meta.append(f"{dataset['likes']:,} likes")

        items.append(
            Item(
                source=DATASETS_KEY,
                identity=identity,
                title=identity,
                # Note the /datasets/ segment, which models do not have.
                url=f"https://huggingface.co/datasets/{identity}",
                text="\n".join(text_parts),
                meta=" · ".join(meta),
            )
        )
    return items, seen


def fetch_papers(run_at):
    dates = [
        run_at.strftime("%Y-%m-%d"),
        (run_at - timedelta(days=1)).strftime("%Y-%m-%d"),
    ]

    by_identity = {}
    seen = []
    for date in dates:
        body = get_json(
            f"https://huggingface.co/api/daily_papers?date={date}&limit=100"
        )
        if not isinstance(body, list):
            raise Unavailable(f"date {date} did not return a JSON array")
        for entry in body:
            paper = entry.get("paper") or {}
            # The arXiv id lives ONLY in the nested paper object, bare, with no
            # `arxiv:` prefix and no version suffix. It is deliberately the same
            # key form as the arXiv Source, which is what makes the dedup a key
            # collision rather than a title match.
            identity = paper.get("id")
            if not identity:
                continue
            if identity not in by_identity:
                seen.append(identity)
            existing = by_identity.get(identity)
            if existing is None or (paper.get("upvotes") or 0) > (
                existing.get("upvotes") or 0
            ):
                by_identity[identity] = paper

    items = []
    for identity, paper in by_identity.items():
        upvotes = paper.get("upvotes") or 0
        items.append(
            Item(
                source=PAPERS_KEY,
                identity=identity,
                title=" ".join((paper.get("title") or identity).split()),
                url=f"https://huggingface.co/papers/{identity}",
                # paper.ai_summary is Hugging Face's own model output and is
                # never a substitute for the Brief's Synopsis; only the
                # abstract is passed to Enrichment.
                text=" ".join((paper.get("summary") or "").split()),
                meta=f"{upvotes:,} upvotes · arXiv {identity}",
            )
        )

    items.sort(key=lambda item: -_upvotes(item))
    return items, seen


def _upvotes(item):
    head = item.meta.split(" upvotes", 1)[0].replace(",", "")
    return int(head) if head.isdigit() else 0
