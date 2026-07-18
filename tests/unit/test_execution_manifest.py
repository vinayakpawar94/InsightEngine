"""Unit tests for insightengine.execution.manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.core.exceptions import ManifestError
from insightengine.execution.manifest import (
    Manifest,
    Stage,
    atomic_write_text,
    load_manifest,
    new_manifest,
    save_manifest,
)


class TestNewManifest:
    def test_has_no_completed_stages(self) -> None:
        manifest = new_manifest()
        assert manifest.completed_stages == frozenset()
        assert manifest.error is None

    def test_run_ids_are_unique(self) -> None:
        assert new_manifest().run_id != new_manifest().run_id


class TestWithCompletedStage:
    def test_adds_to_history(self) -> None:
        manifest = new_manifest().with_completed_stage(Stage.LOADING_DATA)
        assert Stage.LOADING_DATA in manifest.completed_stages
        assert len(manifest.history) == 1

    def test_does_not_mutate_original(self) -> None:
        original = new_manifest()
        updated = original.with_completed_stage(Stage.LOADING_DATA)
        assert original.completed_stages == frozenset()
        assert updated.completed_stages == {Stage.LOADING_DATA}

    def test_clears_previous_error(self) -> None:
        manifest = new_manifest().with_error("boom")
        assert manifest.error == "boom"
        updated = manifest.with_completed_stage(Stage.LOADING_DATA)
        assert updated.error is None

    def test_records_artifact(self) -> None:
        manifest = new_manifest().with_completed_stage(Stage.CLEANING, artifact="cleaned.json")
        assert manifest.artifact_for(Stage.CLEANING) == "cleaned.json"

    def test_artifact_for_missing_stage_is_none(self) -> None:
        manifest = new_manifest()
        assert manifest.artifact_for(Stage.CLEANING) is None

    def test_artifact_for_returns_most_recent_entry(self) -> None:
        manifest = (
            new_manifest()
            .with_completed_stage(Stage.CLEANING, artifact="first.json")
            .with_completed_stage(Stage.CLEANING, artifact="second.json")
        )
        assert manifest.artifact_for(Stage.CLEANING) == "second.json"


class TestWithError:
    def test_records_error_without_touching_history(self) -> None:
        manifest = new_manifest().with_completed_stage(Stage.LOADING_DATA)
        failed = manifest.with_error("something broke")
        assert failed.error == "something broke"
        assert failed.history == manifest.history


class TestAtomicWriteText:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "file.txt"
        atomic_write_text(target, "hello")
        assert target.read_text(encoding="utf-8") == "hello"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        atomic_write_text(target, "first")
        atomic_write_text(target, "second")
        assert target.read_text(encoding="utf-8") == "second"

    def test_no_leftover_temp_file(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        atomic_write_text(target, "hello")
        assert not (tmp_path / "file.txt.tmp").exists()


class TestSaveAndLoadManifest:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        manifest = (
            new_manifest()
            .with_completed_stage(Stage.LOADING_DATA)
            .with_completed_stage(Stage.CLEANING, artifact="cleaned.json")
        )
        save_manifest(manifest, path)
        loaded = load_manifest(path)
        assert loaded.run_id == manifest.run_id
        assert loaded.completed_stages == manifest.completed_stages
        assert loaded.artifact_for(Stage.CLEANING) == "cleaned.json"

    def test_round_trip_with_error(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        manifest = new_manifest().with_error("boom")
        save_manifest(manifest, path)
        loaded = load_manifest(path)
        assert loaded.error == "boom"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ManifestError, match="No manifest found"):
            load_manifest(tmp_path / "does_not_exist.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("not json{{{", encoding="utf-8")
        with pytest.raises(ManifestError, match="not valid JSON"):
            load_manifest(path)

    def test_non_object_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ManifestError, match="JSON object"):
            load_manifest(path)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text('{"run_id": "x"}', encoding="utf-8")
        with pytest.raises(ManifestError, match="malformed"):
            load_manifest(path)

    def test_wrong_type_for_run_id_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text('{"run_id": 123, "created_at": "x", "history": []}', encoding="utf-8")
        with pytest.raises(ManifestError, match="must be strings"):
            load_manifest(path)

    def test_wrong_type_for_error_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": [], "error": 5}', encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="'error' must be a string"):
            load_manifest(path)

    def test_history_not_a_list_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": {}}', encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="'history' must be a list"):
            load_manifest(path)

    def test_history_entry_not_an_object_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": ["not an object"]}',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="must be an object"):
            load_manifest(path)

    def test_history_entry_wrong_field_types_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": '
            '[{"stage": 1, "completed_at": "z"}]}',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="must be strings"):
            load_manifest(path)

    def test_history_entry_wrong_artifact_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": '
            '[{"stage": "loading_data", "completed_at": "z", "artifact": 5}]}',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="'artifact' must be a string"):
            load_manifest(path)

    def test_unrecognized_stage_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"run_id": "x", "created_at": "y", "history": '
            '[{"stage": "bogus_stage", "completed_at": "z"}]}',
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="malformed"):
            load_manifest(path)
