"""Unit tests for insightengine.metadata.validators."""

from __future__ import annotations

import pytest

from insightengine.core.codebook import (
    Category,
    Codebook,
    GridQuestion,
    MultiQuestion,
    NumericQuestion,
    RankingQuestion,
    SingleQuestion,
)
from insightengine.core.exceptions import MetadataParseError
from insightengine.metadata.validators import validate_codebook_authoring


class TestEmptyCodebookCheck:
    def test_empty_codebook_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="zero questions"):
            validate_codebook_authoring(Codebook([]))

    def test_non_empty_codebook_passes(self) -> None:
        validate_codebook_authoring(Codebook([NumericQuestion(id="AGE", label="Age")]))


class TestDuplicateCategoryLabelCheck:
    def test_single_question_with_duplicate_labels_raises(self) -> None:
        q = SingleQuestion(
            id="Q1",
            label="Car?",
            categories=(Category(code=1, label="Yes"), Category(code=2, label="Yes")),
        )
        with pytest.raises(MetadataParseError, match="identical label 'Yes'"):
            validate_codebook_authoring(Codebook([q]))

    def test_single_question_with_distinct_labels_passes(self) -> None:
        q = SingleQuestion(
            id="Q1",
            label="Car?",
            categories=(Category(code=1, label="Yes"), Category(code=2, label="No")),
        )
        validate_codebook_authoring(Codebook([q]))

    def test_multi_question_duplicate_labels_raises(self) -> None:
        q = MultiQuestion(
            id="Q8",
            label="Brands?",
            categories=(Category(code=1, label="Brand A"), Category(code=2, label="Brand A")),
        )
        with pytest.raises(MetadataParseError, match="identical label 'Brand A'"):
            validate_codebook_authoring(Codebook([q]))

    def test_ranking_question_duplicate_item_labels_raises(self) -> None:
        q = RankingQuestion(
            id="Q10",
            label="Rank",
            items=(Category(code=1, label="Price"), Category(code=2, label="Price")),
            rank_count=1,
        )
        with pytest.raises(MetadataParseError, match="identical label 'Price'"):
            validate_codebook_authoring(Codebook([q]))

    def test_grid_question_duplicate_column_labels_raises(self) -> None:
        row = SingleQuestion(id="Q2_1", label="Row", categories=(Category(code=1, label="A"),))
        grid = GridQuestion(
            id="Q2",
            label="Grid",
            rows=(row,),
            columns=(Category(code=1, label="Poor"), Category(code=2, label="Poor")),
        )
        with pytest.raises(MetadataParseError, match="identical label 'Poor'"):
            validate_codebook_authoring(Codebook([grid]))

    def test_numeric_question_has_no_categories_and_is_skipped(self) -> None:
        validate_codebook_authoring(Codebook([NumericQuestion(id="AGE", label="Age")]))
