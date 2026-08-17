"""The material an Edition is made of: an Item, and one Source's answer."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Item:
    """One gathered thing.

    `identity` is the stable key pinned per Source in CONTEXT.md. `text` is
    what Enrichment reads — an abstract, a description, a tag list, or nothing
    at all, which is normal.
    """

    source: str          # a key from config.SOURCE_ORDER
    identity: str
    title: str
    url: str
    text: str = ""
    meta: str = ""       # the human-readable tail of the item-meta line
    rank: int = 0        # position in the Source's pre-Enrichment ranking

    # Set by Enrichment. Both absent together means the Item is Unenriched.
    score: Optional[int] = None
    synopsis: Optional[str] = None
    is_pick: bool = False

    @property
    def unenriched(self) -> bool:
        """An Item with no Score or no Synopsis is Unenriched (CONTEXT.md)."""
        return self.score is None or not (self.synopsis or "").strip()


@dataclass
class SourceResult:
    """What one Source contributed to one Run.

    `unavailable` and an empty `items` list are different states and the page
    says so differently: a Source that answered with nothing new is plain
    grey, an Unavailable Source is ochre with a reason line (#6).
    """

    key: str
    items: List[Item] = field(default_factory=list)
    unavailable: bool = False
    reason: str = ""          # machine-readable, shown on the page
    # Every Identity the Source showed us this Run. Written to the Snapshot on
    # success only; on failure the previous Snapshot is carried forward (#4).
    seen: List[str] = field(default_factory=list)
    # How many Items survived the Snapshot diff and went to Enrichment. A
    # Source that ends with nothing says why: nothing was new, or nothing that
    # was new cleared the cutoff. Those are different sentences on the page.
    considered: int = 0
