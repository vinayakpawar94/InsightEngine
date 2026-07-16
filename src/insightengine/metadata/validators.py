"""Authoring-quality checks for an already-constructed
:class:`~insightengine.core.codebook.Codebook`.

Deliberately does **not** re-check anything
:class:`~insightengine.core.codebook.Codebook` already enforces at
construction time (duplicate ids, circular derived-variable dependencies,
unknown variable references) — that logic lives in exactly one place
(Phase 2), and this module isn't it. Everything here checks things that
are *not* hard structural invariants of the domain model, but are almost
always authoring mistakes: the value-add layer a metadata parser should
provide on top of what the domain model already guarantees.
"""

from __future__ import annotations

from insightengine.core.codebook import (
    Category,
    Codebook,
    GridQuestion,
    MultiQuestion,
    RankingQuestion,
    SingleQuestion,
)
from insightengine.core.exceptions import MetadataParseError


def validate_codebook_authoring(codebook: Codebook) -> None:
    """Run every authoring-quality check against ``codebook``.

    Raises:
        MetadataParseError: On the first check that fails. There is no
            partial-failure/warning-collection mechanism in this phase —
            see the module docstring in
            :mod:`insightengine.metadata.parsers.yaml_native` for why
            that's an explicit, not accidental, scope boundary.
    """
    _require_non_empty(codebook)
    _require_unique_category_labels_per_question(codebook)


def _require_non_empty(codebook: Codebook) -> None:
    """A codebook with zero questions almost always means the parser was
    pointed at an empty or wrong file, not a genuinely empty survey.
    """
    if len(codebook) == 0:
        raise MetadataParseError(
            "Parsed codebook has zero questions. If this is intentional, "
            "this check should be revisited — an empty questionnaire is "
            "an unusual thing to author on purpose."
        )


def _require_unique_category_labels_per_question(codebook: Codebook) -> None:
    """Two categories in the same question sharing an identical label
    under different codes is virtually always a copy-paste mistake — a
    real code duplicate would already be caught by
    :class:`~insightengine.core.exceptions.InvalidQuestionDefinitionError`
    at construction time, but a *label* duplicate with distinct codes
    passes that check silently, since codes (not labels) are what the
    domain model treats as the uniqueness key.
    """
    for question in codebook.questions:
        categories: tuple[Category, ...] | None
        if isinstance(question, (SingleQuestion, MultiQuestion)):
            categories = question.categories
        elif isinstance(question, RankingQuestion):
            categories = question.items
        elif isinstance(question, GridQuestion):
            categories = question.columns
        else:
            categories = None

        if categories is None:
            continue

        seen_labels: dict[str, int] = {}
        for category in categories:
            if category.label in seen_labels:
                raise MetadataParseError(
                    f"Question {question.id!r} has two categories with the "
                    f"identical label {category.label!r} (codes "
                    f"{seen_labels[category.label]} and {category.code}). "
                    f"This is almost always a copy-paste mistake."
                )
            seen_labels[category.label] = category.code
