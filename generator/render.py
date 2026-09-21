"""Emitting the markup.

There is no template engine here on purpose (map note 9): stdlib string
handling only. The markup contracts are the two files this renderer was
written against — `prototype/example-edition.html` for an Edition and the
comment inside `docs/index.html` for the Index — and the class names are the
ubiquitous language, so the emitted HTML and `docs/style.css` read against each
other without translation.

An Edition's date is ONE string. The same `YYYY-MM-DD` goes in the filename,
the URL, the `<time datetime>` and — reformatted only for reading — the `<h1>`,
so those cannot drift apart.
"""

import html
import json
import re
from datetime import datetime

from . import config

EDITION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def e(text):
    return html.escape(text or "", quote=True)


def reading_date(date_string):
    """`2026-08-17` -> `Monday, 17 August 2026`. The visible heading only."""
    return datetime.strptime(date_string, "%Y-%m-%d").strftime("%A, %-d %B %Y")


def short_date(date_string):
    """`2026-08-16` -> `16 August`, for the previous-Edition link."""
    return datetime.strptime(date_string, "%Y-%m-%d").strftime("%-d %B")


def anchor(item):
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", item.identity).strip("-").lower()
    return f"item-{item.source}-{safe}"


# --------------------------------------------------------------------------
# the census
# --------------------------------------------------------------------------


def census(results, picks, model_down, synopsis_down=False):
    """The two lines at the top of every Edition, present on a flawless day too.

    Because the census is always there, a bad day is a different number in a
    line the reader already knows how to read, rather than an alarm they have
    never seen before (#6). Map note 10 lives here.
    """
    total = sum(len(result.items) for result in results.values())
    sources = len(results)
    unavailable = [r for r in results.values() if r.unavailable]
    answered = sources - len(unavailable)
    unenriched = sum(
        1 for r in results.values() for item in r.items if item.unenriched
    )
    # Items carrying both halves; and, separately, Items carrying a Score —
    # which differ once the two halves come from two models.
    scored = total - unenriched
    with_score = sum(
        1 for r in results.values() for item in r.items if item.score is not None
    )
    # Every Item put to Jev, Selected or not. Named only when there were more
    # than the Edition carried, so a day with nothing rejected reads as before.
    considered = sum(len(result.pool) for result in results.values())

    if considered > total and not model_down:
        # More was considered than Selected, so the census names the pool —
        # including the day where everything was considered and nothing
        # Selected, which must not read as a day with no Items at all.
        if total:
            first = (
                f"{total} Item{_s(total)} Selected from {considered} considered "
                f"across {sources} Sources."
            )
        else:
            first = (
                f"No Items Selected from {considered} considered "
                f"across {sources} Sources."
            )
    elif total:
        first = f"{total} Item{_s(total)} across {sources} Sources."
    else:
        first = f"No Items across {sources} Sources."
    if picks:
        first += f" {len(picks)} Pick{_s(len(picks))}."
    else:
        first += ' <span class="hole">No Picks.</span>'

    parts = []
    if unavailable:
        parts.append(
            f"{answered} Source{_s(answered)} answered; "
            f'<span class="hole">{len(unavailable)} Unavailable</span>.'
        )
    else:
        parts.append(f"All {answered} Sources answered.")

    if total == 0:
        pass
    elif unenriched == 0:
        parts.append(
            f"{scored} Item{_s(scored)} carr{'y' if scored != 1 else 'ies'} "
            f"a Score and a Synopsis."
        )
    elif unenriched == total and model_down:
        parts.append(
            f'<span class="hole">All {total} Item{_s(total)} Unenriched</span> — '
            "the model was not reachable during this Run, so nothing today "
            "carries a Score or a Synopsis and nothing could be picked."
        )
    elif unenriched == total and synopsis_down:
        parts.append(
            f"{with_score} Item{_s(with_score)} "
            f"carr{'y' if with_score != 1 else 'ies'} a Score; "
            f'<span class="hole">no Synopsis</span> — the model that writes '
            "them was not reachable during this Run, so every Item carries the "
            "title its Source gave it."
        )
    else:
        parts.append(
            f"{scored} Item{_s(scored)} carr{'y' if scored != 1 else 'ies'} "
            f"a Score and a Synopsis; "
            f'<span class="hole">{unenriched} Unenriched</span>.'
        )

    return first, " ".join(parts), {
        "items": total,
        "sources": sources,
        "picks": len(picks),
        "unavailable": len(unavailable),
        "unenriched": unenriched,
        "considered": considered,
    }


def _s(count):
    return "" if count == 1 else "s"


# --------------------------------------------------------------------------
# an Edition
# --------------------------------------------------------------------------


def edition(date_string, results, picks, model_down, previous_date, synopsis_down=False):
    first_line, second_line, counts = census(results, picks, model_down, synopsis_down)

    out = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="en">')
    out.append("<head>")
    out.append('<meta charset="utf-8">')
    out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    out.append(f"<title>AI Brief — {e(reading_date(date_string))}</title>")
    out.append(
        '<meta name="description" content="%s">'
        % e(
            "The AI Brief for %s: %d Items across %d Sources."
            % (reading_date(date_string), counts["items"], counts["sources"])
        )
    )
    out.append('<link rel="stylesheet" href="style.css">')
    out.append(
        '<link rel="canonical" href="https://mvandewettering.com/ai-brief/%s.html">'
        % date_string
    )
    out.append("</head>")
    out.append("<body>")
    out.append("")
    out.append('<header class="brief-header">')
    out.append('  <p class="brief-title"><a href="index.html">AI Brief</a></p>')
    out.append(
        '  <h1 class="edition-date"><time datetime="%s">%s</time></h1>'
        % (date_string, e(reading_date(date_string)))
    )
    out.append('  <div class="edition-state">')
    out.append(f"    <p>{first_line}</p>")
    out.append(f"    <p>{second_line}</p>")
    out.append("  </div>")
    out.append('  <nav class="edition-nav" aria-label="Edition">')
    out.append("    <ul>")
    out.append('      <li><a href="index.html">All Editions</a></li>')
    if previous_date:
        out.append(
            '      <li><a href="%s.html">Previous: <time datetime="%s">%s</time></a></li>'
            % (previous_date, previous_date, e(short_date(previous_date)))
        )
    out.append("    </ul>")
    out.append("  </nav>")
    out.append("</header>")
    out.append("")
    out.append('<main class="edition">')

    if picks:
        out.append("")
        out.append('  <section class="picks" aria-labelledby="picks-heading">')
        out.append('    <h2 id="picks-heading">Picks</h2>')
        out.append("    <ol>")
        for item in picks:
            out.append(
                '      <li><a href="#%s">%s</a>\n'
                '        <span class="pick-source">%s</span></li>'
                % (anchor(item), e(item.title), e(config.SOURCE_LABELS[item.source]))
            )
        out.append("    </ol>")
        out.append("  </section>")

    if counts["items"] and counts["items"] < 10:
        out.append("")
        out.append(f"  <p class=\"thin-note\">{_thin_note(results, counts)}</p>")

    for key in config.SOURCE_ORDER:
        result = results.get(key)
        if result is None:
            continue
        out.append("")
        out.extend(_source_section(result))

    out.append("")
    out.extend(_decisions(results, model_down))

    out.append("")
    out.append("</main>")
    out.append("")
    out.append("<footer>")
    out.append("  <p>An Edition is published once, and revised only to repair "
               "a Run that failed.</p>")
    out.append('  <p><a href="index.html">All Editions</a></p>')
    out.append("</footer>")
    out.append("")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n", counts


def _thin_note(results, counts):
    """A thin Edition says it is thin, once, and does not repeat the census."""
    total = counts["items"]
    note = (
        f"A quiet day. {total} Item{_s(total)} is a real result, not a "
        "truncation: the Sources that answered had little that was new"
    )
    down = [
        config.SOURCE_LABELS[r.key] for r in results.values() if r.unavailable
    ]
    if down:
        note += ", and the %s that did not %s named below." % (
            "Sources" if len(down) > 1 else "Source",
            "are" if len(down) > 1 else "is",
        )
    else:
        note += "."
    return note


def _source_section(result):
    label = config.SOURCE_LABELS[result.key]
    section_id = f"src-{result.key}"
    lines = []

    if result.unavailable:
        # The section still appears, in its usual place and its usual order.
        # The reader is told what did not happen; they are not shown a shorter
        # page and left to work out that a Source is missing (#6).
        lines.append(
            '  <section class="source source--unavailable" aria-labelledby="%s">'
            % section_id
        )
        lines.append(
            '    <h2 id="%s">%s <span class="source-count">Unavailable</span></h2>'
            % (section_id, e(label))
        )
        lines.append(
            '    <p class="unavailable-note">This Source did not answer during '
            "today's Run, so it contributed no Items to this Edition. Nothing "
            "else about the Edition changed.\n"
            '    <span class="reason">%s</span></p>' % e(result.reason)
        )
        lines.append("  </section>")
        return lines

    count = len(result.items)
    unenriched = sum(1 for item in result.items if item.unenriched)
    if count == 0:
        heading = "no Items"
    elif unenriched == count:
        heading = f"{count} Item{_s(count)}, all Unenriched"
    elif unenriched:
        heading = f"{count} Items, {unenriched} Unenriched"
    else:
        heading = f"{count} Item{_s(count)}"

    lines.append('  <section class="source" aria-labelledby="%s">' % section_id)
    lines.append(
        '    <h2 id="%s">%s <span class="source-count">%s</span></h2>'
        % (section_id, e(label), heading)
    )

    if count == 0:
        # Answered, but contributed nothing. That is different from Unavailable
        # and is said differently: no ochre, no dashed rule, no reason line.
        # The two ways of contributing nothing are also different sentences —
        # a Source that had nothing new did not fail the cutoff, and a Source
        # whose Items all scored below 3 was not quiet.
        if result.considered:
            note = (
                "Answered, and had %d Item%s that %s new, none of which "
                "cleared the cutoff." % (
                    result.considered,
                    _s(result.considered),
                    "were" if result.considered != 1 else "was",
                )
            )
        else:
            note = "Answered, with nothing new since yesterday's Snapshot."
        lines.append('    <p class="thin-note">%s</p>' % note)
        lines.append("  </section>")
        return lines

    lines.append('    <ul class="items">')
    for item in result.items:
        lines.append("")
        lines.extend(_item(item, label))
    lines.append("")
    lines.append("    </ul>")
    lines.append("  </section>")
    return lines


def _item(item, source_label):
    classes = ["item"]
    if item.is_pick:
        classes.append("item--pick")
    if item.unenriched:
        classes.append("item--unenriched")

    lines = [
        '      <li class="%s" id="%s">' % (" ".join(classes), anchor(item)),
        '        <h3 class="item-title"><a href="%s">%s</a></h3>'
        % (e(item.url), e(item.title)),
    ]

    has_score = item.score is not None
    has_synopsis = bool((item.synopsis or "").strip())

    if has_synopsis:
        # The whole Synopsis is on the page: never truncated, never behind a
        # control. The Source's own title stays the link text, so an Enrichment
        # failure never changes where the reader lands.
        lines.append('        <p class="synopsis">%s</p>' % e(item.synopsis))

    meta = []
    if item.is_pick:
        meta.append('<span class="pick-mark">Pick</span>')
    if has_score:
        meta.append('<span class="score">Score %d</span>' % item.score)
    else:
        meta.append("<span>no Score</span>")
    # Score and Synopsis now come from two models and fail independently, so the
    # page says which half is missing rather than assuming neither arrived.
    if not (has_score and has_synopsis):
        meta.append('<span class="state">Unenriched</span>')
    if not has_synopsis:
        tail = item.meta + " · " if item.meta else ""
        meta.append("<span>%stitle as %s gave it</span>" % (e(tail), e(source_label)))
    elif item.meta:
        meta.append("<span>%s</span>" % e(item.meta))

    lines.append('        <p class="item-meta">%s</p>' % "".join(meta))
    lines.append("      </li>")
    return lines


# --------------------------------------------------------------------------
# the day's Decisions
# --------------------------------------------------------------------------


def _number(value):
    """A probability as Jev gave it: 0.71, not 0.7100000000000001."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _plain(key, value):
    """An answer with no scale — the ladder position, a whole number."""
    return (
        '<span class="answer answer--plain">'
        '<span class="answer-key">%s</span>'
        '<span class="answer-value">%s</span></span>'
        % (e(key), e(str(value)))
    )


def _bar(key, value, threshold=None, fired=False):
    """One answer as a track and a number.

    The track carries a tick at the threshold when the question is a noul, and
    fills solid when the rule fired. The number is the text; the track is
    decoration, hidden from assistive technology.
    """
    classes = ["answer"]
    if threshold is not None:
        classes.append("answer--noul")
    if fired:
        classes.append("answer--fired")
    tick = '<span class="bar-tick"></span>' if threshold is not None else ""
    return (
        '<span class="%s">'
        '<span class="answer-key">%s</span>'
        '<span class="bar" aria-hidden="true">'
        '<span class="bar-fill" style="width: %d%%"></span>%s</span>'
        '<span class="answer-value">%s</span></span>'
        % (" ".join(classes), e(key), round(float(value) * 100), tick,
           e(_number(value)))
    )


def _decision(item):
    """One row: the adjusted Score, the Item, and every answer Jev returned."""
    classes = ["decision"]
    if item.selected:
        classes.append("decision--selected")
    if item.score is None and not item.answers:
        classes.append("decision--noanswer")

    if item.selected:
        title = '<a href="#%s">%s</a><span class="decision-mark">Selected</span>' % (
            anchor(item), e(item.title)
        )
    else:
        title = '<a href="%s">%s</a>' % (e(item.url), e(item.title))

    if not item.answers:
        jev = '<span class="no-answer">no answer</span>'
    else:
        bits = []
        if item.raw_score is not None:
            bits.append(_plain("position", item.raw_score))
        if item.score_confidence is not None:
            bits.append(_bar("confidence", item.score_confidence))
        threshold = item.threshold if item.threshold is not None else 1.0
        for name, probability in item.noul.items():
            if probability is None:
                continue
            bits.append(
                _bar(name, probability, threshold=item.threshold,
                     fired=probability >= threshold)
            )
        for note in item.adjustment:
            bits.append('<span class="decision-rule">%s</span>' % e(note))
        jev = "".join(bits)

    return [
        '            <tr class="%s">' % " ".join(classes),
        '              <td class="decision-score">%s</td>'
        % e(str(item.score) if item.score is not None else "—"),
        '              <td class="decision-item">%s</td>' % title,
        '              <td class="decision-source">%s</td>'
        % e(config.SOURCE_LABELS[item.source]),
        '              <td class="decision-jev">%s</td>' % jev,
        "            </tr>",
    ]


def _decisions(results, model_down):
    """The day's Decisions: every Item Jev was shown, at the foot of the page.

    Collapsed, so the Edition above it still reads as the day's queue. The
    ledger is sorted by the adjusted Score, so the cutoff is the boundary
    between the Selected rows and the rest. Two holes are stated here as they
    are elsewhere: a per-Item `no answer` when Jev failed one, and a sentence
    with no table when Jev was unreachable for the Run.
    """
    items = [item for result in results.values() for item in result.pool]
    order = {key: index for index, key in enumerate(config.SOURCE_ORDER)}

    def sort_key(item):
        position = order.get(item.source, len(order))
        if item.score is None:
            return (1, 0, position, item.rank)
        return (0, -item.score, position, item.rank)

    items.sort(key=sort_key)

    lines = [
        '  <section class="decisions" aria-labelledby="decisions-heading">',
        "    <details>",
    ]

    if model_down or not any(item.score is not None for item in items):
        lines.append(
            '      <summary id="decisions-heading">The day\'s Decisions</summary>'
        )
        if model_down:
            note = ("No Decisions. Jev was not reachable during this Run, so "
                    "nothing was scored.")
        else:
            note = ("No Decisions. Jev returned nothing usable for any Item "
                    "this Run.")
        lines.append('      <p class="decisions-empty">%s</p>' % note)
    else:
        lines.append(
            '      <summary id="decisions-heading">The day\'s Decisions'
            '        <span class="decisions-count">%d Item%s</span></summary>'
            % (len(items), _s(len(items)))
        )
        lines.append(
            '      <p class="decisions-note">Every Item Jev was shown, best '
            "Score first. Selected Items are marked; the rest fell below the "
            "cutoff or were trimmed. The Items Jev could not answer are "
            "listed last.</p>"
        )
        lines.append('      <div class="decisions-scroll">')
        lines.append('        <table class="decisions-table">')
        lines.append("          <thead>")
        lines.append("            <tr>")
        lines.append(
            '              <th scope="col" class="decision-score">Score</th>'
        )
        lines.append('              <th scope="col">Item</th>')
        lines.append(
            '              <th scope="col" class="decision-source">Source</th>'
        )
        lines.append('              <th scope="col">Jev\'s answers</th>')
        lines.append("            </tr>")
        lines.append("          </thead>")
        lines.append("          <tbody>")
        cutoff_drawn = False
        for item in items:
            row = _decision(item)
            if (not cutoff_drawn and item.score is not None
                    and item.score < config.CUTOFF):
                row[0] = row[0].replace(
                    'class="decision', 'class="decision decision--cutoff', 1
                )
                cutoff_drawn = True
            lines.extend(row)
        lines.append("          </tbody>")
        lines.append("        </table>")
        lines.append("      </div>")

    lines.append("    </details>")
    lines.append("  </section>")
    return lines


# --------------------------------------------------------------------------
# the Index
# --------------------------------------------------------------------------

MAIN_RE = re.compile(
    r'(<main class="index">)(.*?)(</main>)', re.DOTALL
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def index(existing_html, editions):
    """Rewrite the Index's <main>, preserving the hand-written page around it.

    Everything outside `<main class="index">` — the header, the tagline, the
    footer — is hand-written prose and is left exactly as it was found. Inside,
    the HTML comments are preserved too, because one of them is the markup
    contract this function was written against; only the listing itself is
    regenerated.

    Editions are listed newest first.
    """
    match = MAIN_RE.search(existing_html)
    if not match:
        raise RuntimeError('docs/index.html has no <main class="index"> block')

    out = [""]
    for comment in COMMENT_RE.findall(match.group(2)):
        out.append("  " + comment)
        out.append("")

    if not editions:
        out.append(
            '  <p class="empty">No Editions yet. The generator has not had its '
            "first Run, so there is nothing here to read. This page will list "
            "each day's Edition as soon as one is published.</p>"
        )
    else:
        out.append('  <ol class="editions">')
        for record in editions:
            out.extend(_edition_entry(record))
        out.append("  </ol>")
    out.append("")

    return (
        existing_html[: match.start(2)]
        + "\n".join(out)
        + existing_html[match.end(2):]
    )


def _edition_entry(record):
    date_string = record["date"]
    lines = [
        "    <li>",
        '      <h2 class="edition-link">',
        '        <a href="%s.html"><time datetime="%s">%s</time></a>'
        % (date_string, date_string, e(reading_date(date_string))),
        "      </h2>",
    ]
    # The teaser is the day's first Pick, given as that Item's own title — not
    # a fresh sentence, and never a truncation. With no Picks it is the
    # highest-scoring Item's title, and with neither it is omitted entirely
    # rather than emitted empty.
    if record.get("teaser"):
        lines.append('      <p class="teaser">%s</p>' % e(record["teaser"]))
    lines.append('      <p class="edition-summary">%s</p>' % _summary(record))
    lines.append("    </li>")
    return lines


def _summary(record):
    items, sources = record["items"], record["sources"]
    text = f"{items} Item{_s(items)} across {sources} Sources"
    holes = []
    if record.get("picks"):
        text += f" · {record['picks']} Pick{_s(record['picks'])}"
    else:
        holes.append("no Picks")
    if record.get("unavailable"):
        holes.append(
            f"{record['unavailable']} Source{_s(record['unavailable'])} Unavailable"
        )
    if record.get("unenriched"):
        holes.append(f"{record['unenriched']} Item{_s(record['unenriched'])} Unenriched")
    if holes:
        text += ' · <span class="hole">%s</span>' % e(", ".join(holes))
    return text


def load_editions(state_dir):
    path = state_dir / "editions.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def save_editions(state_dir, editions):
    """The Index's own record, newest first.

    This is not a Snapshot and is deliberately never pruned: it is the archive
    the Index is built from, and a 30-day window would delete the Brief.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "editions.json").write_text(
        json.dumps(editions, indent=1) + "\n", encoding="utf-8"
    )
