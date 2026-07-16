"""Unit tests for insightengine.metadata.parsers.yaml_native."""

from __future__ import annotations

from pathlib import Path

import pytest
import re

from insightengine.core.codebook import (
    DerivedVariable,
    GridQuestion,
    MultiQuestion,
    NumericQuestion,
    RankingQuestion,
    SingleQuestion,
    TextQuestion,
)
from insightengine.core.exceptions import MetadataParseError
from insightengine.metadata.parsers.yaml_native import (
    YamlMetadataParser,
    dump,
    dumps,
    load,
    loads,
)


class TestParseSingleQuestion:
    def test_minimal(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q1
    type: single
    label: "Do you own a car?"
    categories:
      - {code: 1, label: "Yes"}
      - {code: 2, label: "No"}
"""
        )
        q = codebook.get_question("Q1")
        assert isinstance(q, SingleQuestion)
        assert q.label == "Do you own a car?"
        assert q.required is False
        assert [c.code for c in q.categories] == [1, 2]

    def test_required_flag(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q1
    type: single
    label: "Car?"
    required: true
    categories:
      - {code: 1, label: "Yes"}
"""
        )
        assert codebook.get_question("Q1").required is True

    def test_missing_categories_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="missing required field 'categories'"):
            loads(
                """
questions:
  - id: Q1
    type: single
    label: "Car?"
"""
            )


class TestParseMultiQuestion:
    def test_with_max_selections(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q8
    type: multi
    label: "Brands"
    max_selections: 2
    categories:
      - {code: 1, label: "A"}
      - {code: 2, label: "B"}
      - {code: 3, label: "C"}
"""
        )
        q = codebook.get_question("Q8")
        assert isinstance(q, MultiQuestion)
        assert q.max_selections == 2

    def test_without_max_selections(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q8
    type: multi
    label: "Brands"
    categories:
      - {code: 1, label: "A"}
"""
        )
        q = codebook.get_question("Q8")
        assert isinstance(q, MultiQuestion)
        assert q.max_selections is None


class TestParseNumericQuestion:
    def test_bounded(self) -> None:
        codebook = loads(
            """
questions:
  - id: AGE
    type: numeric
    label: "Age"
    min_value: 18
    max_value: 99
"""
        )
        q = codebook.get_question("AGE")
        assert isinstance(q, NumericQuestion)
        assert q.min_value == 18
        assert q.max_value == 99

    def test_unbounded(self) -> None:
        codebook = loads(
            """
questions:
  - id: AGE
    type: numeric
    label: "Age"
"""
        )
        q = codebook.get_question("AGE")
        assert isinstance(q, NumericQuestion)
        assert q.min_value is None
        assert q.max_value is None


class TestParseTextQuestion:
    def test_with_max_length(self) -> None:
        codebook = loads(
            """
questions:
  - id: COMMENTS
    type: text
    label: "Comments"
    max_length: 500
"""
        )
        q = codebook.get_question("COMMENTS")
        assert isinstance(q, TextQuestion)
        assert q.max_length == 500


class TestParseRankingQuestion:
    def test_valid(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q10
    type: ranking
    label: "Rank features"
    rank_count: 2
    items:
      - {code: 1, label: "Price"}
      - {code: 2, label: "Quality"}
      - {code: 3, label: "Service"}
"""
        )
        q = codebook.get_question("Q10")
        assert isinstance(q, RankingQuestion)
        assert q.rank_count == 2
        assert len(q.items) == 3

    def test_missing_rank_count_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="missing required field 'rank_count'"):
            loads(
                """
questions:
  - id: Q10
    type: ranking
    label: "Rank"
    items:
      - {code: 1, label: "A"}
"""
            )


class TestParseGridQuestion:
    def test_rows_inherit_grid_columns_by_default(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q2
    type: grid
    label: "Rate these"
    columns:
      - {code: 1, label: "Poor"}
      - {code: 5, label: "Excellent"}
    rows:
      - {id: Q2_1, label: "Price"}
      - {id: Q2_2, label: "Quality"}
"""
        )
        grid = codebook.get_question("Q2")
        assert isinstance(grid, GridQuestion)
        row1 = codebook.get_question("Q2_1")
        assert isinstance(row1, SingleQuestion)
        assert row1.categories == grid.columns

    def test_row_can_override_type_and_categories(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "Poor"}
      - {code: 5, label: "Excellent"}
    rows:
      - id: Q2_1
        label: "Numeric row"
        type: numeric
        min_value: 0
        max_value: 10
"""
        )
        row = codebook.get_question("Q2_1")
        assert isinstance(row, NumericQuestion)
        assert row.min_value == 0
        assert row.max_value == 10

    def test_row_can_declare_its_own_categories(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "Poor"}
      - {code: 5, label: "Excellent"}
    rows:
      - id: Q2_1
        label: "Different scale row"
        categories:
          - {code: 1, label: "No"}
          - {code: 2, label: "Yes"}
"""
        )
        row = codebook.get_question("Q2_1")
        assert isinstance(row, SingleQuestion)
        assert [c.label for c in row.categories] == ["No", "Yes"]

    def test_unsupported_row_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="unsupported row type 'grid'"):
            loads(
                """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows:
      - {id: Q2_1, label: "Nested", type: grid}
"""
            )


class TestParseDerivedVariable:
    def test_with_dependencies(self) -> None:
        codebook = loads(
            """
questions:
  - id: AGE
    type: numeric
    label: "Age"
  - id: AGE_BAND
    type: derived
    label: "Age band"
    expression: "bucket(AGE)"
    depends_on: [AGE]
"""
        )
        var = codebook.get_question("AGE_BAND")
        assert isinstance(var, DerivedVariable)
        assert var.expression == "bucket(AGE)"
        assert var.depends_on == ("AGE",)

    def test_without_dependencies(self) -> None:
        codebook = loads(
            """
questions:
  - id: CONST
    type: derived
    label: "Constant"
    expression: "1"
"""
        )
        var = codebook.get_question("CONST")
        assert isinstance(var, DerivedVariable)
        assert var.depends_on == ()


class TestParseTopLevelErrors:
    def test_not_a_mapping_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="must be a mapping"):
            loads("- just\n- a\n- list\n")

    def test_missing_questions_key_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="missing required field 'questions'"):
            loads("not_questions: []\n")

    def test_questions_not_a_list_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="'questions' must be a list"):
            loads("questions: {}\n")

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="not valid YAML"):
            loads("questions: [unterminated\n")

    def test_unrecognized_question_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="unrecognized type 'bogus'"):
            loads(
                """
questions:
  - id: Q1
    type: bogus
    label: "X"
"""
            )

    def test_question_entry_not_a_mapping_raises(self) -> None:
        with pytest.raises(MetadataParseError, match=r"questions\[0\] must be a mapping"):
            loads("questions:\n  - just a string\n")

    def test_missing_id_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="missing required field 'id'"):
            loads("questions:\n  - {type: single, label: X}\n")


class TestFieldTypeValidationErrors:
    """Each parsing helper has a 'field present but wrong type' branch
    distinct from its 'field missing' branch — exercised individually
    here rather than only through the 'missing field' tests above.
    """

    def test_require_str_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="must be a non-empty string"):
            loads("questions:\n  - {id: Q1, type: single, label: 123}\n")

    def test_require_str_empty_string_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="must be a non-empty string"):
            loads("questions:\n  - {id: Q1, type: single, label: '   '}\n")

    def test_optional_str_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'type' must be a string"):
            loads(
                """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows:
      - {id: Q2_1, label: "Row", type: 123}
"""
            )

    def test_optional_bool_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="must be a boolean"):
            loads(
                """
questions:
  - id: Q1
    type: single
    label: "X"
    required: "yes"
    categories:
      - {code: 1, label: "A"}
"""
            )

    def test_require_int_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'rank_count' must be an integer"):
            loads(
                """
questions:
  - id: Q10
    type: ranking
    label: "Rank"
    rank_count: "two"
    items:
      - {code: 1, label: "A"}
"""
            )

    def test_optional_int_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'max_selections' must be an integer"):
            loads(
                """
questions:
  - id: Q8
    type: multi
    label: "Brands"
    max_selections: "two"
    categories:
      - {code: 1, label: "A"}
"""
            )

    def test_optional_float_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'min_value' must be a number"):
            loads(
                """
questions:
  - id: AGE
    type: numeric
    label: "Age"
    min_value: "abc"
"""
            )

    def test_require_list_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'rows' must be a list"):
            loads(
                """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows: "not a list"
"""
            )

    def test_optional_list_of_str_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="field 'depends_on' must be a list of strings"):
            loads(
                """
questions:
  - id: AGE
    type: numeric
    label: "Age"
  - id: BAND
    type: derived
    label: "Band"
    expression: "f(AGE)"
    depends_on: "AGE"
"""
            )

    def test_categories_field_wrong_type_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="categories must be a list"):
            loads(
                """
questions:
  - id: Q1
    type: single
    label: "X"
    categories: "not a list"
"""
            )


class TestGridRowTypeCoverage:
    def test_multi_row_with_max_selections(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
      - {code: 2, label: "B"}
    rows:
      - id: Q2_1
        label: "Multi row"
        type: multi
        max_selections: 1
"""
        )
        row = codebook.get_question("Q2_1")
        assert isinstance(row, MultiQuestion)
        assert row.max_selections == 1

    def test_text_row(self) -> None:
        codebook = loads(
            """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows:
      - id: Q2_1
        label: "Text row"
        type: text
        max_length: 100
"""
        )
        row = codebook.get_question("Q2_1")
        assert isinstance(row, TextQuestion)
        assert row.max_length == 100


class TestRowLevelSerializationDetails:
    def test_required_row_round_trips(self) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows:
      - {id: Q2_1, label: "Row", required: true}
"""
        original = loads(source)
        serialized_text = dumps(original)
        assert "required" in serialized_text
        round_tripped = loads(serialized_text)
        assert round_tripped.questions == original.questions

    def test_multi_row_max_selections_round_trips(self) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
      - {code: 2, label: "B"}
    rows:
      - id: Q2_1
        label: "Multi row"
        type: multi
        max_selections: 1
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_text_row_max_length_round_trips(self) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "A"}
    rows:
      - id: Q2_1
        label: "Text row"
        type: text
        max_length: 100
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions


class TestLoadUnreadableFile:
    def test_unreadable_file_raises_metadata_parse_error(self, tmp_path: Path) -> None:
        import os

        path = tmp_path / "codebook.yaml"
        path.write_text("questions: []\n", encoding="utf-8")
        path.chmod(0o000)
        try:
            if os.access(path, os.R_OK):
                pytest.skip("running as a user that bypasses file permissions (e.g. root)")
            with pytest.raises(MetadataParseError, match="Could not read"):
                load(path)
        finally:
            path.chmod(0o644)


class TestLoadFromFile:
    def test_loads_from_a_real_file(self, tmp_path: Path) -> None:
        path = tmp_path / "codebook.yaml"
        path.write_text(
            "questions:\n  - {id: AGE, type: numeric, label: Age}\n", encoding="utf-8"
        )
        codebook = load(path)
        assert "AGE" in codebook

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MetadataParseError, match="not found"):
            load(tmp_path / "does_not_exist.yaml")

    def test_error_message_includes_file_path(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("questions: {}\n", encoding="utf-8")
        #with pytest.raises(MetadataParseError, match=str(path)):
        with pytest.raises(MetadataParseError, match=re.escape(str(path))):
            load(path)


class TestYamlMetadataParser:
    def test_parse_delegates_to_load(self, tmp_path: Path) -> None:
        path = tmp_path / "codebook.yaml"
        path.write_text(
            "questions:\n  - {id: AGE, type: numeric, label: Age}\n", encoding="utf-8"
        )
        codebook = YamlMetadataParser().parse(path)
        assert "AGE" in codebook


class TestRoundTrip:
    def test_simple_codebook_round_trips(self) -> None:
        source = """
questions:
  - id: Q1
    type: single
    label: "Do you own a car?"
    categories:
      - {code: 1, label: "Yes"}
      - {code: 2, label: "No"}
  - id: AGE
    type: numeric
    label: "Age"
    min_value: 18
    max_value: 99
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_grid_with_inherited_row_categories_round_trips_and_omits_categories(
        self,
    ) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Rate these"
    columns:
      - {code: 1, label: "Poor"}
      - {code: 5, label: "Excellent"}
    rows:
      - {id: Q2_1, label: "Price"}
      - {id: Q2_2, label: "Quality"}
"""
        original = loads(source)
        serialized_text = dumps(original)
        # The whole point of inheriting row categories from the grid's
        # columns is that they don't need to be repeated in the source;
        # confirm the serializer actually omits them, not just that
        # re-parsing happens to produce an equal result.
        assert "categories" not in serialized_text

        round_tripped = loads(serialized_text)
        assert round_tripped.questions == original.questions

    def test_grid_with_row_specific_categories_round_trips_with_explicit_categories(
        self,
    ) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "Poor"}
      - {code: 5, label: "Excellent"}
    rows:
      - id: Q2_1
        label: "Different scale"
        categories:
          - {code: 1, label: "No"}
          - {code: 2, label: "Yes"}
"""
        original = loads(source)
        serialized_text = dumps(original)
        assert "categories" in serialized_text

        round_tripped = loads(serialized_text)
        assert round_tripped.questions == original.questions

    def test_grid_with_non_default_row_type_round_trips(self) -> None:
        source = """
questions:
  - id: Q2
    type: grid
    label: "Grid"
    columns:
      - {code: 1, label: "Poor"}
    rows:
      - id: Q2_1
        label: "Numeric row"
        type: numeric
        min_value: 0
        max_value: 10
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_ranking_question_round_trips(self) -> None:
        source = """
questions:
  - id: Q10
    type: ranking
    label: "Rank features"
    rank_count: 2
    items:
      - {code: 1, label: "Price"}
      - {code: 2, label: "Quality"}
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_derived_variable_round_trips(self) -> None:
        source = """
questions:
  - id: AGE
    type: numeric
    label: "Age"
  - id: AGE_BAND
    type: derived
    label: "Age band"
    expression: "bucket(AGE)"
    depends_on: [AGE]
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_required_flag_round_trips(self) -> None:
        source = """
questions:
  - id: Q1
    type: single
    label: "Car?"
    required: true
    categories:
      - {code: 1, label: "Yes"}
"""
        original = loads(source)
        serialized_text = dumps(original)
        assert "required" in serialized_text
        round_tripped = loads(serialized_text)
        assert round_tripped.questions == original.questions

    def test_dump_writes_a_loadable_file(self, tmp_path: Path) -> None:
        original = loads(
            "questions:\n  - {id: AGE, type: numeric, label: Age}\n"
        )
        path = tmp_path / "out.yaml"
        dump(original, path)
        round_tripped = load(path)
        assert round_tripped.questions == original.questions

    def test_multi_question_with_max_selections_round_trips(self) -> None:
        source = """
questions:
  - id: Q8
    type: multi
    label: "Brands"
    max_selections: 2
    categories:
      - {code: 1, label: "A"}
      - {code: 2, label: "B"}
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions

    def test_text_question_with_max_length_round_trips(self) -> None:
        source = """
questions:
  - id: COMMENTS
    type: text
    label: "Comments"
    max_length: 500
"""
        original = loads(source)
        round_tripped = loads(dumps(original))
        assert round_tripped.questions == original.questions
