"""The run manifest: what stage a pipeline run has reached, and what
persisted artifacts exist to resume from.

Writes are atomic (write-to-temp-file-then-``os.replace``), so a process
killed mid-write leaves either the old manifest or the new one fully
intact — never a half-written, corrupt file. ``Path.replace`` is used
specifically because it maps to ``os.replace``, which the standard
library documents as atomic on both POSIX and Windows; ``os.rename``
does not carry the same guarantee on Windows.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum, unique
from pathlib import Path

from insightengine.core.exceptions import ManifestError


@unique
class Stage(StrEnum):
    """A stage in the pipeline's execution sequence, in order."""

    LOADING_DATA = "loading_data"
    LOADING_CODEBOOK = "loading_codebook"
    CLEANING = "cleaning"
    VALIDATING = "validating"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """A record that one stage completed, and what (if anything) it persisted."""

    stage: Stage
    completed_at: str
    artifact: str | None = None


@dataclass(frozen=True, slots=True)
class Manifest:
    """The full state of one pipeline run."""

    run_id: str
    created_at: str
    history: tuple[ManifestEntry, ...] = ()
    error: str | None = None

    @property
    def completed_stages(self) -> frozenset[Stage]:
        """Every stage recorded as complete in this manifest."""
        return frozenset(entry.stage for entry in self.history)

    def with_completed_stage(self, stage: Stage, *, artifact: str | None = None) -> Manifest:
        """Return a new :class:`Manifest` with ``stage`` recorded complete.

        Does not mutate ``self`` — ``Manifest`` is frozen.
        """
        entry = ManifestEntry(
            stage=stage, completed_at=_now_iso(), artifact=artifact
        )
        return replace(self, history=(*self.history, entry), error=None)

    def with_error(self, message: str) -> Manifest:
        """Return a new :class:`Manifest` recording a failure, without
        advancing past whatever stage was in progress.
        """
        return replace(self, error=message)

    def artifact_for(self, stage: Stage) -> str | None:
        """The artifact filename recorded for ``stage``, if any, from the
        most recent entry for that stage.
        """
        for entry in reversed(self.history):
            if entry.stage is stage:
                return entry.artifact
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "history": [
                {
                    "stage": entry.stage.value,
                    "completed_at": entry.completed_at,
                    "artifact": entry.artifact,
                }
                for entry in self.history
            ],
            "error": self.error,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> Manifest:
        try:
            run_id = data["run_id"]
            created_at = data["created_at"]
            error = data.get("error")
            if not isinstance(run_id, str) or not isinstance(created_at, str):
                raise ManifestError("Manifest 'run_id' and 'created_at' must be strings.")
            if error is not None and not isinstance(error, str):
                raise ManifestError("Manifest 'error' must be a string or null.")

            history_raw = data["history"]
            if not isinstance(history_raw, list):
                raise ManifestError(
                    f"Manifest 'history' must be a list, got {type(history_raw).__name__}."
                )
            history = tuple(_entry_from_dict(item) for item in history_raw)

            return Manifest(run_id=run_id, created_at=created_at, history=history, error=error)
        except (KeyError, ValueError, TypeError) as exc:
            raise ManifestError(f"Manifest data is malformed: {exc}") from exc


def _entry_from_dict(item: object) -> ManifestEntry:
    if not isinstance(item, dict):
        raise ManifestError(f"Manifest history entry must be an object, got {type(item).__name__}.")
    stage_raw = item["stage"]
    completed_at = item["completed_at"]
    artifact = item.get("artifact")
    if not isinstance(stage_raw, str) or not isinstance(completed_at, str):
        raise ManifestError("Manifest history entry 'stage' and 'completed_at' must be strings.")
    if artifact is not None and not isinstance(artifact, str):
        raise ManifestError("Manifest history entry 'artifact' must be a string or null.")
    return ManifestEntry(stage=Stage(stage_raw), completed_at=completed_at, artifact=artifact)


def new_manifest() -> Manifest:
    """Create a fresh manifest for a new run, with no completed stages."""
    return Manifest(run_id=str(uuid.uuid4()), created_at=_now_iso())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically.

    Writes to a sibling temp file first, then ``os.replace``s it into
    place — a crash between those two steps leaves the temp file
    orphaned but never leaves ``path`` itself partially written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def save_manifest(manifest: Manifest, path: Path) -> None:
    """Atomically write ``manifest`` to ``path`` as JSON."""
    atomic_write_text(path, json.dumps(manifest.to_dict(), indent=2))


def load_manifest(path: Path) -> Manifest:
    """Read a :class:`Manifest` from ``path``.

    Raises:
        ManifestError: If ``path`` doesn't exist, isn't valid JSON, or
            its contents don't match the expected manifest shape.
    """
    if not path.is_file():
        raise ManifestError(f"No manifest found at {path}.")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest at {path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(
            f"Manifest at {path} must contain a JSON object, got {type(raw).__name__}."
        )
    return Manifest.from_dict(raw)
