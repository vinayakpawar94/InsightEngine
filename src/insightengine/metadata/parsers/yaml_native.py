"""The native YAML questionnaire definition format: parse and serialize.

Schema (informal, matches the platform architecture document's example):

```yaml
questions:
  - id: Q1
    type: single           # single | multi | numeric | text | ranking | grid | derived
    label: "Do you own a car?"
    required: false        # optional, defaults to false
    categories:             # required for single/multi
      - {code: 1, label: "Yes"}
      - {code: 2, label: "No"}
```

Grid rows may omit `categories`/`type` entirely — a row defaults to
`type: single` and, if it declares no categories of its own, inherits
the grid's shared `columns` automatically. This is a parser-level
convenience, not a domain-model feature: Phase 2's ``GridQuestion``
still requires every row to be a fully valid, independently-checkable
``Question`` with its own categories; this parser is simply the thing
that fills them in from the grid's columns so a questionnaire author
doesn't have to repeat the same category list on every row by hand.

Serialization (`dumps`/`dump`) is the literal inverse of parsing: a row
whose categories are identical to its parent grid's columns is written
back without an explicit `categories` key (since the parser will
re-derive the same categories deterministically), and a `type: single`
row omits its `type` key (matching the parser's default).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

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
from insightengine.core.exceptions import MetadataParseError
from insightengine.core.types import QuestionType
from insightengine.metadata.validators import validate_codebook_authoring

_GRID_ROW_TYPES = {"single", "multi", "numeric", "text"}
_TOP_LEVEL_TYPES = {"single", "multi", "numeric", "text", "ranking", "grid", "derived"}


# ---------------------------------------------------------------------------
# Parsing: raw YAML -> Codebook
# ---------------------------------------------------------------------------


def loads(text: str) -> Codebook:
    """Parse a native YAML questionnaire definition from a string.

    Raises:
        MetadataParseError: If the YAML is malformed, structurally
            invalid against the schema, or fails an authoring-quality
            check (see :mod:`insightengine.metadata.validators`).
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MetadataParseError(f"Source is not valid YAML: {exc}") from exc

    top_level = _require_mapping(raw, "top-level document")
    raw_questions = _require_field(top_level, "questions", "top-level document")
    if not isinstance(raw_questions, list):
        raise MetadataParseError(
            f"'questions' must be a list, got {type(raw_questions).__name__}."
        )

    questions = tuple(
        _build_question(item, index) for index, item in enumerate(raw_questions)
    )
    codebook = Codebook(questions)
    validate_codebook_authoring(codebook)
    return codebook


def load(path: Path) -> Codebook:
    """Parse a native YAML questionnaire definition from a file.

    Raises:
        MetadataParseError: If the file doesn't exist, can't be read, or
            fails any check :func:`loads` performs.
    """
    if not path.is_file():
        raise MetadataParseError(f"Metadata file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MetadataParseError(f"Could not read metadata file {path}: {exc}") from exc

    try:
        return loads(text)
    except MetadataParseError as exc:
        raise MetadataParseError(f"In {path}: {exc}") from exc


class YamlMetadataParser:
    """The native-YAML :class:`~insightengine.metadata.base.MetadataParser` implementation."""

    def parse(self, source: Path) -> Codebook:
        return load(source)


# ---------------------------------------------------------------------------
# Parsing helpers — small, sharply-scoped, each raising MetadataParseError
# with a clear field/context reference rather than letting a raw KeyError
# or TypeError surface from deep inside question construction.
# ---------------------------------------------------------------------------


def _require_mapping(raw: object, context: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise MetadataParseError(f"{context} must be a mapping, got {type(raw).__name__}.")
    return raw


def _require_field(raw: Mapping[str, object], key: str, context: str) -> object:
    if key not in raw:
        raise MetadataParseError(f"{context} is missing required field {key!r}.")
    return raw[key]


def _require_str(raw: Mapping[str, object], key: str, context: str) -> str:
    value = _require_field(raw, key, context)
    if not isinstance(value, str) or not value.strip():
        raise MetadataParseError(
            f"{context} field {key!r} must be a non-empty string, got {value!r}."
        )
    return value


def _optional_str(raw: Mapping[str, object], key: str, context: str, *, default: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise MetadataParseError(f"{context} field {key!r} must be a string, got {value!r}.")
    return value


def _optional_bool(raw: Mapping[str, object], key: str, context: str, *, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise MetadataParseError(f"{context} field {key!r} must be a boolean, got {value!r}.")
    return value


def _require_int(raw: Mapping[str, object], key: str, context: str) -> int:
    value = _require_field(raw, key, context)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MetadataParseError(f"{context} field {key!r} must be an integer, got {value!r}.")
    return value


def _optional_int(
    raw: Mapping[str, object], key: str, context: str, *, default: int | None
) -> int | None:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise MetadataParseError(f"{context} field {key!r} must be an integer, got {value!r}.")
    return value


def _optional_float(
    raw: Mapping[str, object], key: str, context: str, *, default: float | None
) -> float | None:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetadataParseError(f"{context} field {key!r} must be a number, got {value!r}.")
    return float(value)


def _require_list(raw: Mapping[str, object], key: str, context: str) -> list[object]:
    value = _require_field(raw, key, context)
    if not isinstance(value, list):
        raise MetadataParseError(
            f"{context} field {key!r} must be a list, got {type(value).__name__}."
        )
    return value


def _optional_list_of_str(
    raw: Mapping[str, object], key: str, context: str, *, default: tuple[str, ...]
) -> tuple[str, ...]:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MetadataParseError(f"{context} field {key!r} must be a list of strings.")
    return tuple(value)


def _build_categories(raw_list: object, context: str) -> tuple[Category, ...]:
    if not isinstance(raw_list, list):
        raise MetadataParseError(
            f"{context} categories must be a list, got {type(raw_list).__name__}."
        )
    categories: list[Category] = []
    for index, raw_category in enumerate(raw_list):
        category_context = f"{context} category[{index}]"
        mapping = _require_mapping(raw_category, category_context)
        code = _require_int(mapping, "code", category_context)
        label = _require_str(mapping, "label", category_context)
        categories.append(Category(code=code, label=label))
    return tuple(categories)


def _build_question(raw: object, index: int) -> Question:
    context = f"questions[{index}]"
    mapping = _require_mapping(raw, context)
    question_id = _require_str(mapping, "id", context)
    context = f"question {question_id!r}"

    label = _require_str(mapping, "label", context)
    type_str = _require_str(mapping, "type", context)
    required = _optional_bool(mapping, "required", context, default=False)

    if type_str not in _TOP_LEVEL_TYPES:
        raise MetadataParseError(
            f"{context} has unrecognized type {type_str!r}. Supported: "
            f"{', '.join(sorted(_TOP_LEVEL_TYPES))}."
        )

    if type_str == "single":
        categories = _build_categories(_require_field(mapping, "categories", context), context)
        return SingleQuestion(id=question_id, label=label, required=required, categories=categories)

    if type_str == "multi":
        categories = _build_categories(_require_field(mapping, "categories", context), context)
        max_selections = _optional_int(mapping, "max_selections", context, default=None)
        return MultiQuestion(
            id=question_id,
            label=label,
            required=required,
            categories=categories,
            max_selections=max_selections,
        )

    if type_str == "numeric":
        min_value = _optional_float(mapping, "min_value", context, default=None)
        max_value = _optional_float(mapping, "max_value", context, default=None)
        return NumericQuestion(
            id=question_id, label=label, required=required, min_value=min_value, max_value=max_value
        )

    if type_str == "text":
        max_length = _optional_int(mapping, "max_length", context, default=None)
        return TextQuestion(id=question_id, label=label, required=required, max_length=max_length)

    if type_str == "ranking":
        items = _build_categories(_require_field(mapping, "items", context), context)
        rank_count = _require_int(mapping, "rank_count", context)
        return RankingQuestion(
            id=question_id, label=label, required=required, items=items, rank_count=rank_count
        )

    if type_str == "grid":
        columns = _build_categories(_require_field(mapping, "columns", context), context)
        raw_rows = _require_list(mapping, "rows", context)
        rows = tuple(
            _build_row(raw_row, columns, context, row_index)
            for row_index, raw_row in enumerate(raw_rows)
        )
        return GridQuestion(id=question_id, label=label, required=required, rows=rows, columns=columns)

    # type_str == "derived" — the only remaining member of _TOP_LEVEL_TYPES.
    expression = _require_str(mapping, "expression", context)
    depends_on = _optional_list_of_str(mapping, "depends_on", context, default=())
    return DerivedVariable(
        id=question_id, label=label, required=required, expression=expression, depends_on=depends_on
    )


def _build_row(
    raw_row: object, grid_columns: tuple[Category, ...], grid_context: str, row_index: int
) -> Question:
    outer_context = f"{grid_context} rows[{row_index}]"
    mapping = _require_mapping(raw_row, outer_context)
    row_id = _require_str(mapping, "id", outer_context)
    row_context = f"{grid_context} row {row_id!r}"

    label = _require_str(mapping, "label", row_context)
    row_type = _optional_str(mapping, "type", row_context, default="single")
    required = _optional_bool(mapping, "required", row_context, default=False)

    if row_type not in _GRID_ROW_TYPES:
        raise MetadataParseError(
            f"{row_context} has unsupported row type {row_type!r}. Grid rows may "
            f"be: {', '.join(sorted(_GRID_ROW_TYPES))}."
        )

    if row_type in ("single", "multi"):
        raw_categories = mapping.get("categories")
        categories = (
            _build_categories(raw_categories, row_context)
            if raw_categories is not None
            else grid_columns
        )
        if row_type == "single":
            return SingleQuestion(id=row_id, label=label, required=required, categories=categories)
        max_selections = _optional_int(mapping, "max_selections", row_context, default=None)
        return MultiQuestion(
            id=row_id,
            label=label,
            required=required,
            categories=categories,
            max_selections=max_selections,
        )

    if row_type == "numeric":
        min_value = _optional_float(mapping, "min_value", row_context, default=None)
        max_value = _optional_float(mapping, "max_value", row_context, default=None)
        return NumericQuestion(
            id=row_id, label=label, required=required, min_value=min_value, max_value=max_value
        )

    # row_type == "text" — the only remaining member of _GRID_ROW_TYPES.
    max_length = _optional_int(mapping, "max_length", row_context, default=None)
    return TextQuestion(id=row_id, label=label, required=required, max_length=max_length)


# ---------------------------------------------------------------------------
# Serialization: Codebook -> raw dict -> YAML
# ---------------------------------------------------------------------------


def serialize_codebook(codebook: Codebook) -> dict[str, object]:
    """Serialize ``codebook`` back into the same raw-dict shape :func:`loads` parses.

    Grid rows are excluded from the top-level list (they're nested under
    their parent grid's ``rows`` key) even though
    :attr:`~insightengine.core.codebook.Codebook.questions` flattens them
    alongside every other question — membership in some grid's own
    ``.rows`` tuple is the ground truth for "this id belongs nested under
    its parent," not insertion position.
    """
    consumed_row_ids: set[str] = set()
    for question in codebook.questions:
        if isinstance(question, GridQuestion):
            consumed_row_ids.update(row.id for row in question.rows)

    top_level = [q for q in codebook.questions if q.id not in consumed_row_ids]
    return {"questions": [_serialize_question(q) for q in top_level]}


def dumps(codebook: Codebook) -> str:
    """Serialize ``codebook`` to a YAML string."""
    return yaml.safe_dump(serialize_codebook(codebook), sort_keys=False, allow_unicode=True)


def dump(codebook: Codebook, path: Path) -> None:
    """Serialize ``codebook`` and write it to ``path`` as YAML."""
    path.write_text(dumps(codebook), encoding="utf-8")


def _serialize_category(category: Category) -> dict[str, object]:
    return {"code": category.code, "label": category.label}


def _serialize_question(question: Question) -> dict[str, object]:
    result: dict[str, object] = {
        "id": question.id,
        "type": question.question_type.value,
        "label": question.label,
    }
    if question.required:
        result["required"] = True

    if isinstance(question, (SingleQuestion, MultiQuestion)):
        result["categories"] = [_serialize_category(c) for c in question.categories]
        if isinstance(question, MultiQuestion) and question.max_selections is not None:
            result["max_selections"] = question.max_selections
    elif isinstance(question, NumericQuestion):
        if question.min_value is not None:
            result["min_value"] = question.min_value
        if question.max_value is not None:
            result["max_value"] = question.max_value
    elif isinstance(question, TextQuestion):
        if question.max_length is not None:
            result["max_length"] = question.max_length
    elif isinstance(question, RankingQuestion):
        result["items"] = [_serialize_category(c) for c in question.items]
        result["rank_count"] = question.rank_count
    elif isinstance(question, GridQuestion):
        result["columns"] = [_serialize_category(c) for c in question.columns]
        result["rows"] = [_serialize_row(row, question.columns) for row in question.rows]
    elif isinstance(question, DerivedVariable):
        result["expression"] = question.expression
        if question.depends_on:
            result["depends_on"] = list(question.depends_on)

    return result


def _serialize_row(row: Question, grid_columns: tuple[Category, ...]) -> dict[str, object]:
    result: dict[str, object] = {"id": row.id, "label": row.label}
    if row.question_type is not QuestionType.SINGLE:
        result["type"] = row.question_type.value
    if row.required:
        result["required"] = True

    if isinstance(row, (SingleQuestion, MultiQuestion)):
        if row.categories != grid_columns:
            result["categories"] = [_serialize_category(c) for c in row.categories]
        if isinstance(row, MultiQuestion) and row.max_selections is not None:
            result["max_selections"] = row.max_selections
    elif isinstance(row, NumericQuestion):
        if row.min_value is not None:
            result["min_value"] = row.min_value
        if row.max_value is not None:
            result["max_value"] = row.max_value
    elif isinstance(row, TextQuestion):
        if row.max_length is not None:
            result["max_length"] = row.max_length

    return result
