"""Unit tests for insightengine.core.codebook."""

from __future__ import annotations

import pytest

from insightengine.core.codebook import (
    Category,
    Codebook,
    DerivedVariable,
    GridQuestion,
    MultiQuestion,
    NumericQuestion,
    Question,
    RankingQuestion,
    SingleQuestion,
    TextQuestion,
)
from insightengine.core.exceptions import (
    CircularDependencyError,
    DuplicateQuestionIdError,
    InvalidQuestionDefinitionError,
    UnknownVariableError,
)
from insightengine.core.types import QuestionType


def _cats(*pairs: tuple[int, str]) -> tuple[Category, ...]:
    return tuple(Category(code=code, label=label) for code, label in pairs)


class TestCategory:
    def test_valid_category(self) -> None:
        category = Category(code=1, label="Yes")
        assert category.code == 1
        assert category.label == "Yes"

    def test_empty_label_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="empty label"):
            Category(code=1, label="   ")

    def test_category_is_frozen(self) -> None:
        category = Category(code=1, label="Yes")
        with pytest.raises(Exception):
            category.label = "No"  # type: ignore[misc]


class TestQuestionAbstractBase:
    def test_cannot_instantiate_question_directly(self) -> None:
        with pytest.raises(TypeError):
            Question(id="Q1", label="Some question")  # type: ignore[abstract]

    def test_empty_id_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="empty"):
            SingleQuestion(id="  ", label="Age", categories=_cats((1, "Yes")))

    def test_empty_label_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="empty label"):
            SingleQuestion(id="Q1", label=" ", categories=_cats((1, "Yes")))


class TestSingleQuestion:
    def test_valid_construction(self) -> None:
        q = SingleQuestion(
            id="Q1",
            label="Do you own a car?",
            categories=_cats((1, "Yes"), (2, "No")),
        )
        assert q.question_type is QuestionType.SINGLE
        assert len(q.categories) == 2
        assert q.required is False

    def test_empty_categories_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="at least one category"):
            SingleQuestion(id="Q1", label="Car?", categories=())

    def test_duplicate_category_codes_raise(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate category code"):
            SingleQuestion(
                id="Q1",
                label="Car?",
                categories=_cats((1, "Yes"), (1, "No")),
            )

    def test_required_flag(self) -> None:
        q = SingleQuestion(
            id="Q1", label="Car?", categories=_cats((1, "Yes")), required=True
        )
        assert q.required is True


class TestMultiQuestion:
    def test_valid_without_max_selections(self) -> None:
        q = MultiQuestion(id="Q8", label="Which brands?", categories=_cats((1, "A"), (2, "B")))
        assert q.question_type is QuestionType.MULTI
        assert q.max_selections is None

    def test_valid_with_max_selections(self) -> None:
        q = MultiQuestion(
            id="Q8",
            label="Which brands?",
            categories=_cats((1, "A"), (2, "B"), (3, "C")),
            max_selections=2,
        )
        assert q.max_selections == 2

    def test_empty_categories_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="at least one category"):
            MultiQuestion(id="Q8", label="Brands?", categories=())

    def test_duplicate_category_codes_raise(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate category code"):
            MultiQuestion(id="Q8", label="Brands?", categories=_cats((1, "A"), (1, "B")))

    def test_max_selections_below_one_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="max_selections"):
            MultiQuestion(
                id="Q8", label="Brands?", categories=_cats((1, "A")), max_selections=0
            )

    def test_max_selections_exceeding_category_count_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="exceeds its category count"):
            MultiQuestion(
                id="Q8",
                label="Brands?",
                categories=_cats((1, "A"), (2, "B")),
                max_selections=5,
            )


class TestNumericQuestion:
    def test_valid_unbounded(self) -> None:
        q = NumericQuestion(id="AGE", label="Age")
        assert q.question_type is QuestionType.NUMERIC
        assert q.min_value is None
        assert q.max_value is None

    def test_valid_bounded(self) -> None:
        q = NumericQuestion(id="AGE", label="Age", min_value=18, max_value=99)
        assert q.min_value == 18
        assert q.max_value == 99

    def test_min_greater_than_max_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="greater than max_value"):
            NumericQuestion(id="AGE", label="Age", min_value=100, max_value=18)

    def test_min_equal_to_max_is_allowed(self) -> None:
        q = NumericQuestion(id="AGE", label="Age", min_value=18, max_value=18)
        assert q.min_value == q.max_value == 18


class TestTextQuestion:
    def test_valid_unbounded(self) -> None:
        q = TextQuestion(id="COMMENTS", label="Any comments?")
        assert q.question_type is QuestionType.TEXT
        assert q.max_length is None

    def test_valid_bounded(self) -> None:
        q = TextQuestion(id="COMMENTS", label="Any comments?", max_length=500)
        assert q.max_length == 500

    def test_max_length_below_one_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="max_length"):
            TextQuestion(id="COMMENTS", label="Any comments?", max_length=0)


class TestRankingQuestion:
    def test_valid_construction(self) -> None:
        q = RankingQuestion(
            id="Q10",
            label="Rank these features",
            items=_cats((1, "Price"), (2, "Quality"), (3, "Service")),
            rank_count=2,
        )
        assert q.question_type is QuestionType.RANKING
        assert q.rank_count == 2

    def test_empty_items_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="at least one item"):
            RankingQuestion(id="Q10", label="Rank", items=(), rank_count=1)

    def test_duplicate_item_codes_raise(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate category code"):
            RankingQuestion(
                id="Q10", label="Rank", items=_cats((1, "A"), (1, "B")), rank_count=1
            )

    def test_rank_count_zero_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="rank_count"):
            RankingQuestion(id="Q10", label="Rank", items=_cats((1, "A")), rank_count=0)

    def test_rank_count_exceeding_item_count_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="rank_count"):
            RankingQuestion(
                id="Q10", label="Rank", items=_cats((1, "A"), (2, "B")), rank_count=3
            )


class TestGridQuestion:
    def test_valid_construction(self) -> None:
        rows = (
            SingleQuestion(id="Q2_1", label="Price", categories=_cats((1, "Poor"))),
            SingleQuestion(id="Q2_2", label="Quality", categories=_cats((1, "Poor"))),
        )
        q = GridQuestion(
            id="Q2",
            label="Rate the following",
            rows=rows,
            columns=_cats((1, "Poor"), (5, "Excellent")),
        )
        assert q.question_type is QuestionType.GRID
        assert len(q.rows) == 2

    def test_empty_rows_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="at least one row"):
            GridQuestion(id="Q2", label="Grid", rows=(), columns=_cats((1, "A")))

    def test_empty_columns_raises(self) -> None:
        row = SingleQuestion(id="Q2_1", label="Row", categories=_cats((1, "A")))
        with pytest.raises(InvalidQuestionDefinitionError, match="at least one column"):
            GridQuestion(id="Q2", label="Grid", rows=(row,), columns=())

    def test_duplicate_column_codes_raise(self) -> None:
        row = SingleQuestion(id="Q2_1", label="Row", categories=_cats((1, "A")))
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate category code"):
            GridQuestion(
                id="Q2", label="Grid", rows=(row,), columns=_cats((1, "A"), (1, "B"))
            )

    def test_duplicate_row_ids_raise(self) -> None:
        row1 = SingleQuestion(id="Q2_1", label="Row1", categories=_cats((1, "A")))
        row2 = SingleQuestion(id="Q2_1", label="Row2", categories=_cats((1, "A")))
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate row id"):
            GridQuestion(id="Q2", label="Grid", rows=(row1, row2), columns=_cats((1, "A")))

    def test_nested_grid_row_raises(self) -> None:
        inner_row = SingleQuestion(id="X_1", label="Inner", categories=_cats((1, "A")))
        nested_grid = GridQuestion(
            id="Q3", label="Nested", rows=(inner_row,), columns=_cats((1, "A"))
        )
        with pytest.raises(InvalidQuestionDefinitionError, match="nested grid"):
            GridQuestion(
                id="Q2", label="Grid", rows=(nested_grid,), columns=_cats((1, "A"))
            )


class TestDerivedVariable:
    def test_valid_construction(self) -> None:
        var = DerivedVariable(
            id="AGE_BAND", label="Age band", expression="bucket(AGE)", depends_on=("AGE",)
        )
        assert var.question_type is QuestionType.DERIVED
        assert var.depends_on == ("AGE",)

    def test_valid_with_no_dependencies(self) -> None:
        var = DerivedVariable(id="CONST", label="Constant", expression="1")
        assert var.depends_on == ()

    def test_empty_expression_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="empty expression"):
            DerivedVariable(id="X", label="X", expression="   ")

    def test_duplicate_dependency_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="duplicate id"):
            DerivedVariable(
                id="X", label="X", expression="A+A", depends_on=("A", "A")
            )

    def test_self_dependency_raises(self) -> None:
        with pytest.raises(InvalidQuestionDefinitionError, match="cannot depend on itself"):
            DerivedVariable(id="X", label="X", expression="X+1", depends_on=("X",))


class TestCodebookBasics:
    def test_construction_and_lookup(self) -> None:
        q1 = SingleQuestion(id="Q1", label="Car?", categories=_cats((1, "Yes"), (2, "No")))
        q2 = NumericQuestion(id="AGE", label="Age")
        codebook = Codebook([q1, q2])

        assert len(codebook) == 2
        assert "Q1" in codebook
        assert "AGE" in codebook
        assert "Q99" not in codebook
        assert codebook.get_question("Q1") is q1
        assert codebook.questions == (q1, q2)

    def test_get_unknown_question_raises(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        with pytest.raises(UnknownVariableError, match="Q99"):
            codebook.get_question("Q99")

    def test_duplicate_top_level_id_raises(self) -> None:
        q1 = NumericQuestion(id="AGE", label="Age")
        q2 = NumericQuestion(id="AGE", label="Age again")
        with pytest.raises(DuplicateQuestionIdError, match="AGE"):
            Codebook([q1, q2])

    def test_empty_codebook_is_valid(self) -> None:
        codebook = Codebook([])
        assert len(codebook) == 0
        assert codebook.questions == ()
        assert codebook.derived_variables() == ()


class TestCodebookGridFlattening:
    def test_grid_rows_are_individually_addressable(self) -> None:
        row1 = SingleQuestion(id="Q2_1", label="Price", categories=_cats((1, "A")))
        row2 = SingleQuestion(id="Q2_2", label="Quality", categories=_cats((1, "A")))
        grid = GridQuestion(
            id="Q2", label="Rate these", rows=(row1, row2), columns=_cats((1, "Poor"))
        )
        codebook = Codebook([grid])

        assert len(codebook) == 3  # grid itself + 2 rows
        assert codebook.get_question("Q2") is grid
        assert codebook.get_question("Q2_1") is row1
        assert codebook.get_question("Q2_2") is row2

    def test_grid_row_id_colliding_with_another_top_level_question_raises(self) -> None:
        row = SingleQuestion(id="DUPLICATE", label="Row", categories=_cats((1, "A")))
        grid = GridQuestion(
            id="Q2", label="Grid", rows=(row,), columns=_cats((1, "A"))
        )
        other = NumericQuestion(id="DUPLICATE", label="Other")
        with pytest.raises(DuplicateQuestionIdError, match="DUPLICATE"):
            Codebook([grid, other])


class TestCodebookDerivedVariables:
    def test_unknown_dependency_raises_at_construction(self) -> None:
        var = DerivedVariable(id="X", label="X", expression="Y+1", depends_on=("Y",))
        with pytest.raises(UnknownVariableError, match="Y"):
            Codebook([var])

    def test_dependency_on_directly_collected_question_is_fine(self) -> None:
        age = NumericQuestion(id="AGE", label="Age")
        band = DerivedVariable(
            id="AGE_BAND", label="Age band", expression="bucket(AGE)", depends_on=("AGE",)
        )
        codebook = Codebook([age, band])
        assert codebook.derived_variables() == (band,)

    def test_circular_dependency_raises_at_construction_not_lazily(self) -> None:
        a = DerivedVariable(id="A", label="A", expression="B+1", depends_on=("B",))
        b = DerivedVariable(id="B", label="B", expression="A+1", depends_on=("A",))
        with pytest.raises(CircularDependencyError):
            Codebook([a, b])

    def test_three_level_dependency_chain_computes_correct_order(self) -> None:
        base = NumericQuestion(id="AGE", label="Age")
        level1 = DerivedVariable(
            id="AGE_BAND", label="Band", expression="bucket(AGE)", depends_on=("AGE",)
        )
        level2 = DerivedVariable(
            id="AGE_GROUP",
            label="Group",
            expression="group(AGE_BAND)",
            depends_on=("AGE_BAND",),
        )
        level3 = DerivedVariable(
            id="AGE_SEGMENT",
            label="Segment",
            expression="segment(AGE_GROUP)",
            depends_on=("AGE_GROUP",),
        )
        # Constructed in a deliberately scrambled order to prove the
        # ordering comes from dependency analysis, not input order.
        codebook = Codebook([level3, base, level1, level2])

        order = [var.id for var in codebook.derived_variables()]
        assert order.index("AGE_BAND") < order.index("AGE_GROUP")
        assert order.index("AGE_GROUP") < order.index("AGE_SEGMENT")

    def test_three_way_cycle_raises(self) -> None:
        a = DerivedVariable(id="A", label="A", expression="C+1", depends_on=("C",))
        b = DerivedVariable(id="B", label="B", expression="A+1", depends_on=("A",))
        c = DerivedVariable(id="C", label="C", expression="B+1", depends_on=("B",))
        with pytest.raises(CircularDependencyError):
            Codebook([a, b, c])

    def test_diamond_dependency_is_not_a_false_positive_cycle(self) -> None:
        # AGE -> BAND -> {LEFT, RIGHT} -> COMBINED : a diamond, not a cycle.
        age = NumericQuestion(id="AGE", label="Age")
        band = DerivedVariable(id="BAND", label="Band", expression="f(AGE)", depends_on=("AGE",))
        left = DerivedVariable(id="LEFT", label="Left", expression="g(BAND)", depends_on=("BAND",))
        right = DerivedVariable(
            id="RIGHT", label="Right", expression="h(BAND)", depends_on=("BAND",)
        )
        combined = DerivedVariable(
            id="COMBINED",
            label="Combined",
            expression="LEFT+RIGHT",
            depends_on=("LEFT", "RIGHT"),
        )
        codebook = Codebook([age, band, left, right, combined])
        order = [var.id for var in codebook.derived_variables()]
        assert order.index("BAND") < order.index("LEFT")
        assert order.index("BAND") < order.index("RIGHT")
        assert order.index("LEFT") < order.index("COMBINED")
        assert order.index("RIGHT") < order.index("COMBINED")

    def test_derived_variables_excludes_non_derived_questions(self) -> None:
        age = NumericQuestion(id="AGE", label="Age")
        band = DerivedVariable(id="BAND", label="Band", expression="f(AGE)", depends_on=("AGE",))
        codebook = Codebook([age, band])
        assert all(isinstance(v, DerivedVariable) for v in codebook.derived_variables())
        assert len(codebook.derived_variables()) == 1
