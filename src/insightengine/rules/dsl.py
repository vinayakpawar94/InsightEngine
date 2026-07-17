"""Rule representation and the YAML rule parser.

Seven rule types, matching the implementation roadmap's committed scope
for this phase exactly — no more, no less:

* :class:`RangeRule` / :class:`SkipLogicRule` / a bare :class:`RequiredRule`
  wrap a :class:`~insightengine.rules.evaluator.CompiledExpression` —
  the only place this module touches the security-critical evaluator.
* :class:`SumEqualsRule`, :class:`MaxSelectionsRule`,
  :class:`ExclusiveCategoryRule`, :class:`RankRule` are pure structured
  data with their own internal validity checks — no free-text expression
  at all, so there's no expression-language surface to secure for these.

This module does **not** execute any rule against real data (no
``evaluate_rule(rule, dataset) -> ...``) — that's Phase 6 (Validation
Execution), which needs a real ``Codebook``/``DataHandle`` to be
meaningful. What's here is the same evaluator-decoupled shape as
:mod:`insightengine.rules.evaluator` itself: a rule's own
``CompiledExpression`` fields can already be evaluated against a plain
variable mapping, but nothing here reaches into a dataset to do it.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from insightengine.core.exceptions import InvalidRuleDefinitionError, RuleParseError
from insightengine.core.types import Severity
from insightengine.rules.evaluator import CompiledExpression, compile_expression

_RULE_TYPES = {
    "range",
    "required",
    "skip_logic",
    "sum_equals",
    "max_selections",
    "exclusive_category",
    "rank",
}


@dataclass(frozen=True, kw_only=True, slots=True)
class Rule(ABC):
    """Abstract base for every rule type.

    Args:
        id: Unique identifier for this rule within a rule set.
        severity: How serious a violation of this rule is.
        message: Optional human-readable message. If ``None``, whatever
            consumes rule results (Phase 6/Phase 9) is expected to
            generate a default message from the rule's own fields — this
            class doesn't generate one itself, since a good default
            message depends on the specific rule type's semantics.
    """

    id: str
    severity: Severity = Severity.ERROR
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidRuleDefinitionError("A rule id cannot be empty.")


@dataclass(frozen=True, kw_only=True, slots=True)
class RangeRule(Rule):
    """A bare condition rule: violated when ``when`` evaluates truthy.

    Named to match the roadmap's rule-type list, but not restricted to
    numeric ranges — per the platform architecture document's rule
    engine design, "range validation" is just one instance of a plain
    ``when:`` condition, not a distinct grammar of its own.
    """

    when: CompiledExpression


@dataclass(frozen=True, kw_only=True, slots=True)
class RequiredRule(Rule):
    """``variable`` must be answered, optionally only when ``when`` holds.

    Args:
        when: If ``None``, ``variable`` is unconditionally required. If
            set, ``variable`` is required only when this evaluates truthy.
    """

    variable: str
    when: CompiledExpression | None = None

    def __post_init__(self) -> None:
        super(RequiredRule, self).__post_init__()
        if not self.variable.strip():
            raise InvalidRuleDefinitionError(f"Rule {self.id!r}: variable cannot be empty.")


@dataclass(frozen=True, kw_only=True, slots=True)
class SkipLogicRule(Rule):
    """The "apply-or-nullify" pattern: the most common shape in the
    business rules knowledge base's rule catalogue.

    Args:
        when: The gate condition.
        then_required: Variables that must be answered when ``when`` is true.
        else_variables: Variables that must be *blank* when ``when`` is
            false. Distinct from ``then_required`` because the set of
            variables that become required and the set that must be
            nulled-out on the other branch aren't always identical in
            real questionnaires (though they often are).
    """

    when: CompiledExpression
    then_required: tuple[str, ...]
    else_variables: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super(SkipLogicRule, self).__post_init__()
        if not self.then_required:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: then_required cannot be empty."
            )
        if len(set(self.then_required)) != len(self.then_required):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: duplicate variable in then_required."
            )
        if len(set(self.else_variables)) != len(self.else_variables):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: duplicate variable in else_variables."
            )


@dataclass(frozen=True, kw_only=True, slots=True)
class SumEqualsRule(Rule):
    """``variables`` must sum to ``target``, within ``tolerance``."""

    variables: tuple[str, ...]
    target: float
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        super(SumEqualsRule, self).__post_init__()
        if len(self.variables) < 2:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: needs at least 2 variables to sum, got "
                f"{len(self.variables)}."
            )
        if len(set(self.variables)) != len(self.variables):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: duplicate variable in variables."
            )
        if self.tolerance < 0:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: tolerance cannot be negative."
            )


@dataclass(frozen=True, kw_only=True, slots=True)
class MaxSelectionsRule(Rule):
    """``variable`` (a multi-response question) may have at most
    ``max_selections`` categories selected.
    """

    variable: str
    max_selections: int

    def __post_init__(self) -> None:
        super(MaxSelectionsRule, self).__post_init__()
        if not self.variable.strip():
            raise InvalidRuleDefinitionError(f"Rule {self.id!r}: variable cannot be empty.")
        if self.max_selections < 1:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: max_selections must be >= 1, got {self.max_selections}."
            )


@dataclass(frozen=True, kw_only=True, slots=True)
class ExclusiveCategoryRule(Rule):
    """``variable``'s ``exclusive_codes`` may not be selected alongside
    any other category in the same multi-response answer.
    """

    variable: str
    exclusive_codes: tuple[int, ...]

    def __post_init__(self) -> None:
        super(ExclusiveCategoryRule, self).__post_init__()
        if not self.variable.strip():
            raise InvalidRuleDefinitionError(f"Rule {self.id!r}: variable cannot be empty.")
        if not self.exclusive_codes:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: exclusive_codes cannot be empty."
            )
        if len(set(self.exclusive_codes)) != len(self.exclusive_codes):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: duplicate code in exclusive_codes."
            )


@dataclass(frozen=True, kw_only=True, slots=True)
class RankRule(Rule):
    """The compound rank-validation shape found identically four times
    in the business rules knowledge base: an optional exclusive/none
    flag gates whether ranking applies at all, a bound on how many slots
    must be filled, a bound on each slot's rank value, and an optional
    "other" text requirement.

    Args:
        rank_variables: The slot variables holding rank positions.
        exclusive_flag_variable: If set, this variable being truthy means
            the whole rank block doesn't apply to this case.
        min_ranked: Minimum number of ``rank_variables`` that must be filled.
        max_ranked: Maximum number that may be filled. Defaults to
            ``len(rank_variables)`` (all of them) if ``None``.
        min_rank_value: Minimum allowed value in a filled rank slot.
        max_rank_value: Maximum allowed value in a filled rank slot
            (e.g. 3 for a "rank your top 3" question).
        other_variable: Optional "other" category's flag variable.
        other_text_variable: Required alongside ``other_variable`` — the
            free-text variable that must be non-empty when the "other"
            category is used. Both or neither must be set.
    """

    rank_variables: tuple[str, ...]
    exclusive_flag_variable: str | None = None
    min_ranked: int = 1
    max_ranked: int | None = None
    min_rank_value: int = 1
    max_rank_value: int = 1
    other_variable: str | None = None
    other_text_variable: str | None = None

    def __post_init__(self) -> None:
        super(RankRule, self).__post_init__()
        if not self.rank_variables:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: rank_variables cannot be empty."
            )
        if len(set(self.rank_variables)) != len(self.rank_variables):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: duplicate variable in rank_variables."
            )

        effective_max_ranked = (
            self.max_ranked if self.max_ranked is not None else len(self.rank_variables)
        )
        if not (1 <= self.min_ranked <= effective_max_ranked <= len(self.rank_variables)):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: min_ranked ({self.min_ranked}) / max_ranked "
                f"({effective_max_ranked}) out of bounds for "
                f"{len(self.rank_variables)} rank_variables."
            )
        if self.min_rank_value > self.max_rank_value:
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: min_rank_value ({self.min_rank_value}) is "
                f"greater than max_rank_value ({self.max_rank_value})."
            )
        if (self.other_variable is None) != (self.other_text_variable is None):
            raise InvalidRuleDefinitionError(
                f"Rule {self.id!r}: other_variable and other_text_variable must "
                f"both be set or both omitted."
            )


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------


def parse_rules(text: str) -> tuple[Rule, ...]:
    """Parse a YAML rule-set definition into a tuple of :class:`Rule` objects.

    Raises:
        RuleParseError: If the YAML is malformed, structurally invalid
            against the schema, or two rules share the same id.
        UnsafeExpressionError: If any ``when:`` expression uses a
            disallowed construct — see :mod:`insightengine.rules.evaluator`.
        InvalidRuleDefinitionError: If a rule's own fields are internally
            inconsistent (e.g. a ``RankRule`` with ``min_ranked >
            max_ranked``).
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RuleParseError(f"Source is not valid YAML: {exc}") from exc

    top_level = _require_mapping(raw, "top-level document")
    raw_rules = _require_field(top_level, "rules", "top-level document")
    if not isinstance(raw_rules, list):
        raise RuleParseError(f"'rules' must be a list, got {type(raw_rules).__name__}.")

    rules = tuple(_build_rule(item, index) for index, item in enumerate(raw_rules))

    seen_ids: set[str] = set()
    for rule in rules:
        if rule.id in seen_ids:
            raise RuleParseError(f"Duplicate rule id {rule.id!r}.")
        seen_ids.add(rule.id)

    return rules


def load_rules(path: Path) -> tuple[Rule, ...]:
    """Parse a YAML rule-set definition from a file. See :func:`parse_rules`."""
    if not path.is_file():
        raise RuleParseError(f"Rules file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuleParseError(f"Could not read rules file {path}: {exc}") from exc

    try:
        return parse_rules(text)
    except RuleParseError as exc:
        raise RuleParseError(f"In {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Parsing helpers. Deliberately duplicated from (not shared with)
# insightengine.metadata.parsers.yaml_native's private helpers of the same
# shape — that module is frozen from a completed, reviewed phase, and this
# phase doesn't reopen it. See this module's docstring.
# ---------------------------------------------------------------------------


def _require_mapping(raw: object, context: str) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        raise RuleParseError(f"{context} must be a mapping, got {type(raw).__name__}.")
    return raw


def _require_field(raw: Mapping[str, object], key: str, context: str) -> object:
    if key not in raw:
        raise RuleParseError(f"{context} is missing required field {key!r}.")
    return raw[key]


def _require_str(raw: Mapping[str, object], key: str, context: str) -> str:
    value = _require_field(raw, key, context)
    if not isinstance(value, str) or not value.strip():
        raise RuleParseError(
            f"{context} field {key!r} must be a non-empty string, got {value!r}."
        )
    return value


def _optional_str(
    raw: Mapping[str, object], key: str, context: str, *, default: str | None
) -> str | None:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if not isinstance(value, str):
        raise RuleParseError(f"{context} field {key!r} must be a string, got {value!r}.")
    return value


def _require_int(raw: Mapping[str, object], key: str, context: str) -> int:
    value = _require_field(raw, key, context)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuleParseError(f"{context} field {key!r} must be an integer, got {value!r}.")
    return value


def _optional_int(
    raw: Mapping[str, object], key: str, context: str, *, default: int | None
) -> int | None:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuleParseError(f"{context} field {key!r} must be an integer, got {value!r}.")
    return value


def _require_number(raw: Mapping[str, object], key: str, context: str) -> float:
    value = _require_field(raw, key, context)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleParseError(f"{context} field {key!r} must be a number, got {value!r}.")
    return float(value)


def _optional_number(
    raw: Mapping[str, object], key: str, context: str, *, default: float
) -> float:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleParseError(f"{context} field {key!r} must be a number, got {value!r}.")
    return float(value)


def _require_list_of_str(raw: Mapping[str, object], key: str, context: str) -> tuple[str, ...]:
    value = _require_field(raw, key, context)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuleParseError(f"{context} field {key!r} must be a list of strings.")
    return tuple(value)


def _optional_list_of_str(
    raw: Mapping[str, object], key: str, context: str, *, default: tuple[str, ...]
) -> tuple[str, ...]:
    if key not in raw or raw[key] is None:
        return default
    value = raw[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuleParseError(f"{context} field {key!r} must be a list of strings.")
    return tuple(value)


def _require_list_of_int(raw: Mapping[str, object], key: str, context: str) -> tuple[int, ...]:
    value = _require_field(raw, key, context)
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise RuleParseError(f"{context} field {key!r} must be a list of integers.")
    return tuple(value)


def _severity_from_raw(raw: Mapping[str, object], context: str) -> Severity:
    value = _optional_str(raw, "severity", context, default=Severity.ERROR.value)
    assert value is not None  # default is a string, never None
    try:
        return Severity(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in Severity)
        raise RuleParseError(
            f"{context} field 'severity' has unrecognized value {value!r}. "
            f"Supported: {allowed}."
        ) from exc


def _build_rule(raw: object, index: int) -> Rule:
    context = f"rules[{index}]"
    mapping = _require_mapping(raw, context)
    rule_id = _require_str(mapping, "id", context)
    context = f"rule {rule_id!r}"

    type_str = _require_str(mapping, "type", context)
    if type_str not in _RULE_TYPES:
        raise RuleParseError(
            f"{context} has unrecognized type {type_str!r}. Supported: "
            f"{', '.join(sorted(_RULE_TYPES))}."
        )

    severity = _severity_from_raw(mapping, context)
    message = _optional_str(mapping, "message", context, default=None)

    if type_str == "range":
        range_when = compile_expression(_require_str(mapping, "when", context))
        return RangeRule(id=rule_id, severity=severity, message=message, when=range_when)

    if type_str == "required":
        variable = _require_str(mapping, "variable", context)
        raw_when = mapping.get("when")
        required_when = compile_expression(raw_when) if isinstance(raw_when, str) else None
        return RequiredRule(
            id=rule_id,
            severity=severity,
            message=message,
            variable=variable,
            when=required_when,
        )

    if type_str == "skip_logic":
        skip_logic_when = compile_expression(_require_str(mapping, "when", context))
        then_required = _require_list_of_str(mapping, "then_required", context)
        else_variables = _optional_list_of_str(mapping, "else_variables", context, default=())
        return SkipLogicRule(
            id=rule_id,
            severity=severity,
            message=message,
            when=skip_logic_when,
            then_required=then_required,
            else_variables=else_variables,
        )

    if type_str == "sum_equals":
        variables = _require_list_of_str(mapping, "variables", context)
        target = _require_number(mapping, "target", context)
        tolerance = _optional_number(mapping, "tolerance", context, default=0.0)
        return SumEqualsRule(
            id=rule_id,
            severity=severity,
            message=message,
            variables=variables,
            target=target,
            tolerance=tolerance,
        )

    if type_str == "max_selections":
        variable = _require_str(mapping, "variable", context)
        max_selections = _require_int(mapping, "max_selections", context)
        return MaxSelectionsRule(
            id=rule_id,
            severity=severity,
            message=message,
            variable=variable,
            max_selections=max_selections,
        )

    if type_str == "exclusive_category":
        variable = _require_str(mapping, "variable", context)
        exclusive_codes = _require_list_of_int(mapping, "exclusive_codes", context)
        return ExclusiveCategoryRule(
            id=rule_id,
            severity=severity,
            message=message,
            variable=variable,
            exclusive_codes=exclusive_codes,
        )

    # type_str == "rank" — the only remaining member of _RULE_TYPES.
    rank_variables = _require_list_of_str(mapping, "rank_variables", context)
    exclusive_flag_variable = _optional_str(
        mapping, "exclusive_flag_variable", context, default=None
    )
    min_ranked = _optional_int(mapping, "min_ranked", context, default=1)
    max_ranked = _optional_int(mapping, "max_ranked", context, default=None)
    min_rank_value = _optional_int(mapping, "min_rank_value", context, default=1)
    max_rank_value = _optional_int(mapping, "max_rank_value", context, default=1)
    other_variable = _optional_str(mapping, "other_variable", context, default=None)
    other_text_variable = _optional_str(mapping, "other_text_variable", context, default=None)
    assert min_rank_value is not None and max_rank_value is not None and min_ranked is not None
    return RankRule(
        id=rule_id,
        severity=severity,
        message=message,
        rank_variables=rank_variables,
        exclusive_flag_variable=exclusive_flag_variable,
        min_ranked=min_ranked,
        max_ranked=max_ranked,
        min_rank_value=min_rank_value,
        max_rank_value=max_rank_value,
        other_variable=other_variable,
        other_text_variable=other_text_variable,
    )
