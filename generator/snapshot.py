"""Snapshots: one Source's recorded set of Identities from one Run.

An Item is *new* when its Identity is absent from the Snapshots, which is how
Sources that publish no useful timestamps are read at all. The file keeps a
rolling 30-day window (map note 5) and the diff is taken against the whole
retained window rather than yesterday alone — an Item that dropped out of a
trending top-30 and climbed back is not new, and a second Run on the same day
must see the first Run's Items as already seen.

State is committed on purpose; see the comment in .gitignore.
"""

import json
from datetime import datetime, timedelta, timezone

from . import config


class SnapshotStore:
    def __init__(self, state_dir):
        self.state_dir = state_dir

    def _path(self, key):
        return self.state_dir / f"{key}.json"

    def load(self, key):
        path = self._path(key)
        if not path.exists():
            return {"source": key, "snapshots": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            # A corrupt Snapshot must not stop a Run. The Source simply has no
            # history this morning and everything it returns looks new.
            return {"source": key, "snapshots": []}
        if not isinstance(data, dict) or not isinstance(data.get("snapshots"), list):
            return {"source": key, "snapshots": []}
        return data

    def known(self, key):
        """Every Identity inside the retained window, as a set."""
        identities = set()
        for snapshot in self.load(key)["snapshots"]:
            identities.update(snapshot.get("identities") or [])
        return identities

    def record(self, key, run_date, identities):
        """Append this Run's Snapshot and prune. Called on success only.

        If a Source was Unavailable this is not called at all, so its previous
        Snapshot is carried forward untouched and the next successful Run still
        sees the right "new" set (#4).
        """
        data = self.load(key)
        snapshots = [s for s in data["snapshots"] if s.get("date") != run_date]
        snapshots.append(
            {
                "date": run_date,
                "recorded_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "identities": sorted(set(identities)),
            }
        )
        snapshots = _prune(snapshots, run_date)
        data["source"] = key
        data["snapshots"] = snapshots

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(
            json.dumps(data, indent=1, sort_keys=False) + "\n", encoding="utf-8"
        )


def _prune(snapshots, run_date):
    horizon = (
        datetime.strptime(run_date, "%Y-%m-%d")
        - timedelta(days=config.SNAPSHOT_WINDOW_DAYS)
    ).strftime("%Y-%m-%d")
    kept = [s for s in snapshots if (s.get("date") or "") > horizon]
    kept.sort(key=lambda s: s.get("date") or "")
    return kept
