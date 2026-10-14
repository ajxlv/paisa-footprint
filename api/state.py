"""Per-app settings and the lazily loaded snapshot, shared with routes via a dependency."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from pf_core.snapshot import Snapshot, load_snapshot


@dataclass
class AppState:
    """Where the app reads from. The snapshot loads on first use, so a missing one gives a clear
    503 with the command to build it, rather than a crash at import."""

    snapshot_dir: Path
    demo_dir: Path
    docs_dir: Path

    @cached_property
    def snapshot(self) -> Snapshot:
        if not (self.snapshot_dir / "companies.parquet").exists():
            raise HTTPException(
                503,
                f"No snapshot in {self.snapshot_dir}. Run: pf build-snapshot "
                f"--input tests/fixtures/brsr --out {self.snapshot_dir}",
            )
        return load_snapshot(self.snapshot_dir)


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.pf
    return state


State = Annotated[AppState, Depends(get_state)]
