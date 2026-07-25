"""Unit tests for insightengine.migration.sav_legacy.

Two tiers, matching the module's own stated verification status:

* Variable/value-label reading is tested against **real ``.sav`` files**,
  created and read back with ``pyreadstat`` itself.
* MRSET handling cannot be tested this way — ``pyreadstat.write_sav``
  has no parameter for writing MRSET definitions (confirmed by
  inspecting its signature). Those tests monkeypatch
  ``pyreadstat.read_sav`` to return a metadata object shaped exactly per
  ``pyreadstat``'s own documented ``MRSet`` TypedDict — a controlled
  simulation of a real file, not a real file, and the tests say so.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyreadstat
import pytest

from insightengine.core.codebook import MultiQuestion, NumericQuestion, SingleQuestion, TextQuestion
from insightengine.core.exceptions import MetadataParseError
from insightengine.migration.sav_legacy import SavMetadataParser, _coerce_label_key


class TestCoerceLabelKey:
    def test_int_passes_through(self) -> None:
        assert _coerce_label_key(2) == 2

    def test_whole_number_float_coerces(self) -> None:
        assert _coerce_label_key(2.0) == 2

    def test_fractional_float_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="not a whole number"):
            _coerce_label_key(2.5)

    def test_bool_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="boolean"):
            _coerce_label_key(True)


class TestRealSavFileImport:
    """Genuinely real: writes an actual .sav file with pyreadstat, then
    imports it with SavMetadataParser and checks the result.
    """

    def test_numeric_variable_without_labels(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"AGE": [25, 30, 45]})
        path = tmp_path / "test.sav"
        pyreadstat.write_sav(df, str(path), column_labels=["Respondent age"])

        codebook = SavMetadataParser().parse(path)
        question = codebook.get_question("AGE")
        assert isinstance(question, NumericQuestion)
        assert question.label == "Respondent age"

    def test_text_variable(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"COMMENTS": ["good", "bad", "ok"]})
        path = tmp_path / "test.sav"
        pyreadstat.write_sav(df, str(path))

        codebook = SavMetadataParser().parse(path)
        question = codebook.get_question("COMMENTS")
        assert isinstance(question, TextQuestion)

    def test_categorical_variable_with_value_labels(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"GENDER": [1, 2, 1]})
        path = tmp_path / "test.sav"
        pyreadstat.write_sav(
            df,
            str(path),
            variable_value_labels={"GENDER": {1: "Male", 2: "Female"}},
            column_labels=["Respondent gender"],
        )

        codebook = SavMetadataParser().parse(path)
        question = codebook.get_question("GENDER")
        assert isinstance(question, SingleQuestion)
        assert question.label == "Respondent gender"
        codes_and_labels = {c.code: c.label for c in question.categories}
        assert codes_and_labels == {1: "Male", 2: "Female"}

    def test_label_falls_back_to_variable_name_when_unlabeled(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"AGE": [25]})
        path = tmp_path / "test.sav"
        pyreadstat.write_sav(df, str(path))

        codebook = SavMetadataParser().parse(path)
        assert codebook.get_question("AGE").label == "AGE"

    def test_multiple_variables_all_imported(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"AGE": [25], "GENDER": [1], "COMMENTS": ["ok"]})
        path = tmp_path / "test.sav"
        pyreadstat.write_sav(
            df, str(path), variable_value_labels={"GENDER": {1: "Male"}}
        )

        codebook = SavMetadataParser().parse(path)
        assert len(codebook) == 3

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MetadataParseError, match="not found"):
            SavMetadataParser().parse(tmp_path / "does_not_exist.sav")

    def test_corrupt_file_raises_metadata_parse_error(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.sav"
        path.write_bytes(b"this is not a real sav file")
        with pytest.raises(MetadataParseError, match="Could not read"):
            SavMetadataParser().parse(path)


class _FakeMeta:
    """Simulates a pyreadstat metadata_container shaped exactly per its
    real, confirmed attributes — used only because no real MRSET-bearing
    .sav file, and no way to write one with pyreadstat, is available.
    """

    def __init__(
        self,
        column_names: list[str],
        column_names_to_labels: dict[str, str],
        variable_value_labels: dict[str, dict[Any, str]],
        readstat_variable_types: dict[str, str],
        mr_sets: dict[str, dict[str, Any]],
    ) -> None:
        self.column_names = column_names
        self.column_names_to_labels = column_names_to_labels
        self.variable_value_labels = variable_value_labels
        self.readstat_variable_types = readstat_variable_types
        self.mr_sets = mr_sets


class TestMrsetHandlingSimulated:
    """MRSET tests via monkeypatched pyreadstat.read_sav — a controlled
    simulation matching pyreadstat's own documented MRSet shape, not a
    real file. See this module's and sav_legacy's docstrings.
    """

    def test_dichotomy_mrset_becomes_multi_question(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_meta = _FakeMeta(
            column_names=["Q8A", "Q8B", "Q8C"],
            column_names_to_labels={"Q8A": "Brand A", "Q8B": "Brand B", "Q8C": "Brand C"},
            variable_value_labels={},
            readstat_variable_types={"Q8A": "double", "Q8B": "double", "Q8C": "double"},
            mr_sets={
                "$Q8": {
                    "type": "D",
                    "is_dichotomy": True,
                    "counted_value": 1,
                    "label": "Brands used",
                    "variable_list": ["Q8A", "Q8B", "Q8C"],
                }
            },
        )
        monkeypatch.setattr(
            "insightengine.migration.sav_legacy.pyreadstat.read_sav",
            lambda path, metadataonly=True: (None, fake_meta),
        )

        path = tmp_path / "fake.sav"
        path.write_bytes(b"placeholder")  # only needs to exist for the is_file() check
        codebook = SavMetadataParser().parse(path)

        mrset_question = codebook.get_question("$Q8")
        assert isinstance(mrset_question, MultiQuestion)
        assert mrset_question.label == "Brands used"
        codes_and_labels = {c.code: c.label for c in mrset_question.categories}
        assert codes_and_labels == {1: "Brand A", 2: "Brand B", 3: "Brand C"}

        # The constituent variables are represented once, via the MRSET,
        # not also as their own standalone questions.
        assert "Q8A" not in codebook
        assert "Q8B" not in codebook
        assert len(codebook) == 1

    def test_category_mrset_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_meta = _FakeMeta(
            column_names=["Q9A", "Q9B"],
            column_names_to_labels={},
            variable_value_labels={},
            readstat_variable_types={"Q9A": "double", "Q9B": "double"},
            mr_sets={
                "$Q9": {
                    "type": "C",
                    "is_dichotomy": False,
                    "counted_value": None,
                    "label": "Top brands",
                    "variable_list": ["Q9A", "Q9B"],
                }
            },
        )
        monkeypatch.setattr(
            "insightengine.migration.sav_legacy.pyreadstat.read_sav",
            lambda path, metadataonly=True: (None, fake_meta),
        )

        path = tmp_path / "fake.sav"
        path.write_bytes(b"placeholder")
        with pytest.raises(MetadataParseError, match="multiple category"):
            SavMetadataParser().parse(path)

    def test_mrset_with_empty_variable_list_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_meta = _FakeMeta(
            column_names=[],
            column_names_to_labels={},
            variable_value_labels={},
            readstat_variable_types={},
            mr_sets={
                "$Q10": {
                    "type": "D",
                    "is_dichotomy": True,
                    "counted_value": 1,
                    "label": "Empty set",
                    "variable_list": [],
                }
            },
        )
        monkeypatch.setattr(
            "insightengine.migration.sav_legacy.pyreadstat.read_sav",
            lambda path, metadataonly=True: (None, fake_meta),
        )

        path = tmp_path / "fake.sav"
        path.write_bytes(b"placeholder")
        with pytest.raises(MetadataParseError, match="no constituent variables"):
            SavMetadataParser().parse(path)
