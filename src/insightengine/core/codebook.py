"""The core domain model: :class:`Category`, the :class:`Question` hierarchy,
and :class:`Codebook`.

This module models the *questionnaire design*, not the physical dataset a
respondent's answers end up stored in. A :class:`GridQuestion`, for
example, describes rows/columns as a survey designer thinks about them;
how those rows and columns materialize into actual data columns is the
Cleaning Engine's job (Phase 7), not this module's.

Every class here is an immutable, frozen dataclass. Domain objects are
constructed once (typically by a metadata parser, Phase 4) and never
mutated afterward — a `Codebook` that could change out from under a
running validation/cleaning pipeline would be a source of exactly the
kind of subtle bugs this framework exists to eliminate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from insightengine.core.exceptions import (
    CircularDependencyError,
    DuplicateQuestionIdError,
    InvalidQuestionDefinitionError,
    UnknownVariableError,
)
from insightengine.core.types import QuestionType


@dataclass(frozen=True, slots=True)
class Category:
    """One answer option for a categorical, multi-response, ranking, or
    grid-column question.

    Args:
        code: The numeric code stored in the data for this category.
            Deliberately ``int``, matching the numeric category-code
            convention confirmed in the Dimensions knowledge base
            (``MDM.CategoryMap.AutoAssignValues()``) — not a design
            invented for this framework.
        label: Human-readable text for this category.
    """

    code: int
    label: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise InvalidQuestionDefinitionError(
                f"Category with code {self.code} has an empty label."
            )


def _require_unique_codes(categories: Sequence[Category], owner_id: str) -> None:
    """Raise :class:`InvalidQuestionDefinitionError` if ``categories``
    contains two entries with the same ``code``.
    """
    seen: set[int] = set()
    for category in categories:
        if category.code in seen:
            raise InvalidQuestionDefinitionError(
                f"Question {owner_id!r} has duplicate category code {category.code}."
            )
        seen.add(category.code)


@dataclass(frozen=True, kw_only=True, slots=True)
class Question(ABC):
    """Abstract base for every kind of question/variable in a codebook.

    Args:
        id: The unique identifier other questions, rules, and datasets
            use to refer to this question (e.g. ``"Q1"``).
        label: Human-readable question text.
        required: Whether this question must be answered. Note this is
            the question's own *unconditional* required-ness; conditional
            requirement ("Q2 is required only if Q1 == Yes") is a Rule
            Engine concern (Phase 5's ``SkipLogicRule``), not modeled here.
    """

    id: str
    label: str
    required: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidQuestionDefinitionError("A question id cannot be empty.")
        if not self.label.strip():
            raise InvalidQuestionDefinitionError(f"Question {self.id!r} has an empty label.")

    @property
    @abstractmethod
    def question_type(self) -> QuestionType:
        """The :class:`~insightengine.core.types.QuestionType` this question represents."""
        raise NotImplementedError  # pragma: no cover


@dataclass(frozen=True, kw_only=True, slots=True)
class SingleQuestion(Question):
    """A single-response categorical question (pick exactly one)."""

    categories: tuple[Category, ...]

    def __post_init__(self) -> None:
        super(SingleQuestion, self).__post_init__()
        if not self.categories:
            raise InvalidQuestionDefinitionError(
                f"SingleQuestion {self.id!r} must have at least one category."
            )
        _require_unique_codes(self.categories, self.id)

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.SINGLE


@dataclass(frozen=True, kw_only=True, slots=True)
class MultiQuestion(Question):
    """A multiple-response categorical question (pick any number).

    Args:
        max_selections: Optional cap on how many categories may be
            selected — this is the metadata-level fact ("this question
            allows up to 3 picks"); enforcing it against real data is a
            Rule Engine concern (the ``max_selections`` rule pattern from
            the business rules knowledge base), not this class's job.
    """

    categories: tuple[Category, ...]
    max_selections: int | None = None

    def __post_init__(self) -> None:
        super(MultiQuestion, self).__post_init__()
        if not self.categories:
            raise InvalidQuestionDefinitionError(
                f"MultiQuestion {self.id!r} must have at least one category."
            )
        _require_unique_codes(self.categories, self.id)
        if self.max_selections is not None:
            if self.max_selections < 1:
                raise InvalidQuestionDefinitionError(
                    f"MultiQuestion {self.id!r} max_selections must be >= 1, "
                    f"got {self.max_selections}."
                )
            if self.max_selections > len(self.categories):
                raise InvalidQuestionDefinitionError(
                    f"MultiQuestion {self.id!r} max_selections "
                    f"({self.max_selections}) exceeds its category count "
                    f"({len(self.categories)})."
                )

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.MULTI


@dataclass(frozen=True, kw_only=True, slots=True)
class NumericQuestion(Question):
    """A free-entry numeric question, optionally bounded."""

    min_value: float | None = None
    max_value: float | None = None

    def __post_init__(self) -> None:
        super(NumericQuestion, self).__post_init__()
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise InvalidQuestionDefinitionError(
                f"NumericQuestion {self.id!r} has min_value ({self.min_value}) "
                f"greater than max_value ({self.max_value})."
            )

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.NUMERIC


@dataclass(frozen=True, kw_only=True, slots=True)
class TextQuestion(Question):
    """A free-entry text (open-end) question."""

    max_length: int | None = None

    def __post_init__(self) -> None:
        super(TextQuestion, self).__post_init__()
        if self.max_length is not None and self.max_length < 1:
            raise InvalidQuestionDefinitionError(
                f"TextQuestion {self.id!r} max_length must be >= 1, got {self.max_length}."
            )

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.TEXT


@dataclass(frozen=True, kw_only=True, slots=True)
class RankingQuestion(Question):
    """A ranking question: the respondent orders (some of) a set of items.

    Args:
        items: The full set of rankable items.
        rank_count: How many of ``items`` must actually be ranked (the
            "top-k" depth) — this is the compound rank-validation shape
            found identically across four real questions in the business
            rules knowledge base (an exclusive/none flag, a count bound,
            and a per-slot value bound). The exclusive-flag and count
            checks against real data are Rule Engine concerns; this class
            only records the static shape (how many items exist, how many
            of them must be ranked).
    """

    items: tuple[Category, ...]
    rank_count: int

    def __post_init__(self) -> None:
        super(RankingQuestion, self).__post_init__()
        if not self.items:
            raise InvalidQuestionDefinitionError(
                f"RankingQuestion {self.id!r} must have at least one item."
            )
        _require_unique_codes(self.items, self.id)
        if not (1 <= self.rank_count <= len(self.items)):
            raise InvalidQuestionDefinitionError(
                f"RankingQuestion {self.id!r} rank_count ({self.rank_count}) must be "
                f"between 1 and its item count ({len(self.items)})."
            )

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.RANKING


@dataclass(frozen=True, kw_only=True, slots=True)
class GridQuestion(Question):
    """A grid/matrix question: a set of row sub-questions sharing one
    column scale.

    Args:
        rows: The row sub-questions. Each row's own :attr:`Question.id`
            is a genuine, independently addressable variable id (it will
            appear as its own column in real data) — grids are flattened
            into the parent :class:`Codebook`'s id namespace, not hidden
            behind the grid's own id. See :class:`Codebook`.
        columns: The shared answer scale (e.g. a 1–5 rating scale) applied
            to every row.
    """

    rows: tuple[Question, ...]
    columns: tuple[Category, ...]

    def __post_init__(self) -> None:
        super(GridQuestion, self).__post_init__()
        if not self.rows:
            raise InvalidQuestionDefinitionError(
                f"GridQuestion {self.id!r} must have at least one row."
            )
        if not self.columns:
            raise InvalidQuestionDefinitionError(
                f"GridQuestion {self.id!r} must have at least one column."
            )
        _require_unique_codes(self.columns, self.id)

        row_ids: set[str] = set()
        for row in self.rows:
            if isinstance(row, GridQuestion):
                raise InvalidQuestionDefinitionError(
                    f"GridQuestion {self.id!r} cannot have a nested grid as a row "
                    f"(row {row.id!r})."
                )
            if row.id in row_ids:
                raise InvalidQuestionDefinitionError(
                    f"GridQuestion {self.id!r} has duplicate row id {row.id!r}."
                )
            row_ids.add(row.id)

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.GRID


@dataclass(frozen=True, kw_only=True, slots=True)
class DerivedVariable(Question):
    """A variable computed from other variables rather than collected
    directly from a respondent.

    Args:
        expression: The computation, as an opaque string at this layer.
            **Phase 2 does not parse or evaluate this expression** — that
            is the Rule/Cleaning Engine's job (Phases 5/7), which will use
            the same restricted expression evaluator as the Rule Engine
            rather than a second, independently-trusted evaluator. This
            class's only responsibility is recording *that* a derivation
            exists and *what it depends on*, so the codebook can detect
            circular dependencies and compute a safe evaluation order
            before any evaluator ever runs.
        depends_on: The ids of every variable this expression reads from.
            Declared explicitly rather than inferred from parsing
            ``expression`` — inferring it would require this layer to
            understand the expression grammar, which is exactly the
            coupling to the Rule Engine this class is designed to avoid.
    """

    expression: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super(DerivedVariable, self).__post_init__()
        if not self.expression.strip():
            raise InvalidQuestionDefinitionError(
                f"DerivedVariable {self.id!r} has an empty expression."
            )
        if len(set(self.depends_on)) != len(self.depends_on):
            raise InvalidQuestionDefinitionError(
                f"DerivedVariable {self.id!r} lists a duplicate id in depends_on."
            )
        if self.id in self.depends_on:
            raise InvalidQuestionDefinitionError(
                f"DerivedVariable {self.id!r} cannot depend on itself."
            )

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.DERIVED


def _flatten(question: Question) -> Iterable[Question]:
    """Yield ``question`` itself, and — if it is a :class:`GridQuestion`
    — every one of its rows too, since each row is its own addressable
    variable id in the codebook's flat namespace.
    """
    yield question
    if isinstance(question, GridQuestion):
        yield from question.rows


def _compute_derivation_order(derived: dict[str, DerivedVariable]) -> tuple[str, ...]:
    """Topologically sort derived-variable ids so that every dependency
    comes before its dependent, using Kahn's algorithm.

    Only edges between two derived variables participate in the graph —
    a dependency on a directly-collected question is a leaf input with no
    ordering constraint of its own. Ties are broken alphabetically so the
    result is deterministic and testable.

    Raises:
        CircularDependencyError: If the derived variables' dependencies
            contain a cycle.
    """
    in_degree: dict[str, int] = dict.fromkeys(derived, 0)
    dependents: dict[str, list[str]] = {var_id: [] for var_id in derived}

    for var_id, variable in derived.items():
        for dependency_id in variable.depends_on:
            if dependency_id in derived:
                dependents[dependency_id].append(var_id)
                in_degree[var_id] += 1

    ready: deque[str] = deque(sorted(var_id for var_id, deg in in_degree.items() if deg == 0))
    order: list[str] = []

    while ready:
        var_id = ready.popleft()
        order.append(var_id)
        for dependent_id in sorted(dependents[var_id]):
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                ready.append(dependent_id)

    if len(order) != len(derived):
        unresolved = sorted(set(derived) - set(order))
        raise CircularDependencyError(
            "Circular dependency detected among derived variables: "
            + ", ".join(unresolved)
        )
    return tuple(order)


class Codebook:
    """An immutable collection of :class:`Question` objects forming one
    survey's complete metadata.

    Construction validates the whole collection eagerly:

    * every question (and every grid row, flattened into the same
      namespace) has a unique id — :class:`DuplicateQuestionIdError`;
    * every :class:`DerivedVariable`'s ``depends_on`` entries refer to
      ids that actually exist in this codebook —
      :class:`UnknownVariableError`;
    * the derived variables' dependencies contain no cycle —
      :class:`CircularDependencyError`, raised at construction time, not
      lazily when something later tries to evaluate them.
    """

    def __init__(self, questions: Iterable[Question]) -> None:
        self._questions: dict[str, Question] = {}

        for top_level_question in questions:
            for question in _flatten(top_level_question):
                if question.id in self._questions:
                    raise DuplicateQuestionIdError(
                        f"Duplicate question id {question.id!r}."
                    )
                self._questions[question.id] = question

        derived = {
            question.id: question
            for question in self._questions.values()
            if isinstance(question, DerivedVariable)
        }
        for variable in derived.values():
            for dependency_id in variable.depends_on:
                if dependency_id not in self._questions:
                    raise UnknownVariableError(
                        f"DerivedVariable {variable.id!r} depends on unknown "
                        f"variable {dependency_id!r}."
                    )

        self._derivation_order: tuple[str, ...] = _compute_derivation_order(derived)

    @property
    def questions(self) -> tuple[Question, ...]:
        """All questions in this codebook, in insertion order, including
        grid rows flattened alongside their parent grid.
        """
        return tuple(self._questions.values())

    def get_question(self, question_id: str) -> Question:
        """Look up a question by id.

        Raises:
            UnknownVariableError: If no question with this id exists.
        """
        try:
            return self._questions[question_id]
        except KeyError as exc:
            raise UnknownVariableError(f"Unknown question id {question_id!r}.") from exc

    def __contains__(self, question_id: str) -> bool:
        return question_id in self._questions

    def __len__(self) -> int:
        return len(self._questions)

    def derived_variables(self) -> tuple[DerivedVariable, ...]:
        """All :class:`DerivedVariable` questions in this codebook, in
        dependency order (a variable never appears before something it
        depends on).
        """
        derived = {
            question.id: question
            for question in self._questions.values()
            if isinstance(question, DerivedVariable)
        }
        return tuple(derived[var_id] for var_id in self._derivation_order)
