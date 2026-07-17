"""Executes a set of :class:`~insightengine.rules.dsl.Rule` objects, plus
built-in codebook-domain checks, against real data.

**Scope decisions for this phase, stated once here rather than repeated
at every call site:**

1. **"Vectorized" means column-pulled-once, not numpy-level.** Every
   variable a rule or domain check needs is fetched via
   :meth:`~insightengine.data.base.DataHandle.column` exactly once and
   reused across all rows, rather than re-querying per case (the
   ``OnNextCase`` model this project moved away from) — but comparisons
   still loop over rows in Python. Phase 3's frozen ``DataHandle``
   protocol has no columnar boolean-mask API; adding one would mean
   reopening that phase.
2. **``RankRule`` is not executed here.** :func:`validate` raises
   :class:`~insightengine.core.exceptions.RuleEvaluationError` immediately
   if one is passed in — an explicit, loud gap rather than a silently
   skipped rule that could let bad data through unnoticed.
3. **Multi-response convention:** a :class:`~insightengine.core.codebook.MultiQuestion`
   answer is a ``list``/``tuple``/``set``/``frozenset`` of selected
   category codes, or ``None``. Raw CSV-sourced string data is not in
   this shape without a conversion step (Phase 7's job).
4. **A row with a missing value in a numeric aggregate (``SumEqualsRule``)
   is skipped for that rule, not flagged by it** — whether missing data
   itself is a problem is a :class:`~insightengine.rules.dsl.RequiredRule`'s
   job, not an aggregate rule's.
"""

from __future__ import annotations

from collections.abc import Sequence

from insightengine.core.codebook import (
    DerivedVariable,
    GridQuestion,
    MultiQuestion,
    NumericQuestion,
    Question,
    RankingQuestion,
    SingleQuestion,
    TextQuestion,
)
from insightengine.core.exceptions import RuleEvaluationError, UnknownVariableError
from insightengine.core.types import Severity
from insightengine.rules.dsl import (
    ExclusiveCategoryRule,
    MaxSelectionsRule,
    RangeRule,
    RankRule,
    RequiredRule,
    Rule,
    SkipLogicRule,
    SumEqualsRule,
)
from insightengine.validation.collector import ErrorCollector
from insightengine.validation.context import ValidationContext
from insightengine.validation.results import ValidationResult


def validate(context: ValidationContext, rules: Sequence[Rule]) -> ErrorCollector:
    """Run every built-in codebook-domain check plus every rule in
    ``rules`` against ``context``'s data, returning all violations found.

    Raises:
        RuleEvaluationError: If ``rules`` contains a :class:`RankRule`
            (execution deferred, see this module's docstring) or if a
            rule references data that doesn't match its expected shape
            (e.g. a non-numeric value where a sum is expected).
        UnknownVariableError: If a rule references a variable name that
            isn't a column in ``context.data``.
    """
    for rule in rules:
        if isinstance(rule, RankRule):
            raise RuleEvaluationError(
                f"Rule {rule.id!r}: RankRule execution is deferred, not "
                f"implemented in this phase. See the implementation roadmap."
            )

    collector = ErrorCollector()
    _validate_codebook_domains(context, collector)

    row_variables: list[dict[str, object]] | None = None
    for rule in rules:
        if isinstance(rule, (RangeRule, RequiredRule, SkipLogicRule)):
            if row_variables is None:
                row_variables = _build_row_variables(context)
            _execute_expression_rule(rule, row_variables, collector)
        elif isinstance(rule, SumEqualsRule):
            _execute_sum_equals_rule(rule, context, collector)
        elif isinstance(rule, MaxSelectionsRule):
            _execute_max_selections_rule(rule, context, collector)
        elif isinstance(rule, ExclusiveCategoryRule):
            _execute_exclusive_category_rule(rule, context, collector)

    return collector


def _is_missing(value: object) -> bool:
    """Whether a value counts as "not answered."

    Only ``None`` counts. Whether an empty string from a data source
    should also count as missing is a source-specific normalization
    concern (the Cleaning Engine's job, Phase 7), not this layer's.
    """
    return value is None


def _build_row_variables(context: ValidationContext) -> list[dict[str, object]]:
    """Pull every column in the dataset exactly once, then zip into one
    dict per row — the mechanism every expression-based rule
    (:class:`RangeRule`, :class:`RequiredRule`, :class:`SkipLogicRule`)
    shares, built once per :func:`validate` call rather than once per rule.
    """
    names = context.data.column_names
    columns = {name: context.data.column(name) for name in names}
    return [{name: columns[name][i] for name in names} for i in range(context.data.row_count)]


def _execute_expression_rule(
    rule: RangeRule | RequiredRule | SkipLogicRule,
    row_variables: list[dict[str, object]],
    collector: ErrorCollector,
) -> None:
    if isinstance(rule, RangeRule):
        for row_index, variables in enumerate(row_variables):
            if bool(rule.when.evaluate(variables)):
                collector.add(
                    ValidationResult(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=rule.message or f"Rule {rule.id!r} violated: {rule.when.source}",
                        row_index=row_index,
                    )
                )
        return

    if isinstance(rule, RequiredRule):
        for row_index, variables in enumerate(row_variables):
            if rule.variable not in variables:
                raise UnknownVariableError(
                    f"Rule {rule.id!r} references unknown variable {rule.variable!r}."
                )
            gate = True if rule.when is None else bool(rule.when.evaluate(variables))
            if gate and _is_missing(variables[rule.variable]):
                collector.add(
                    ValidationResult(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=rule.message or f"{rule.variable} is required.",
                        row_index=row_index,
                        variables=(rule.variable,),
                    )
                )
        return

    # SkipLogicRule — the only remaining member of the union.
    for row_index, variables in enumerate(row_variables):
        gate = bool(rule.when.evaluate(variables))
        target_variables = rule.then_required if gate else rule.else_variables
        for var in target_variables:
            if var not in variables:
                raise UnknownVariableError(
                    f"Rule {rule.id!r} references unknown variable {var!r}."
                )
            missing = _is_missing(variables[var])
            violated = (missing if gate else not missing)
            if violated:
                if gate:
                    message = rule.message or f"{var} is required when {rule.when.source}."
                else:
                    message = (
                        rule.message
                        or f"{var} should be blank when not ({rule.when.source})."
                    )
                collector.add(
                    ValidationResult(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=message,
                        row_index=row_index,
                        variables=(var,),
                    )
                )


def _as_selection(value: object, rule_id: str, variable: str, row_index: int) -> set[object] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise RuleEvaluationError(
            f"Rule {rule_id!r}: expected a collection of selected codes for "
            f"{variable!r} in row {row_index}, got {type(value).__name__}."
        )
    result: set[object] = set()
    for item in value:
        result.add(item)
    return result


def _execute_sum_equals_rule(
    rule: SumEqualsRule, context: ValidationContext, collector: ErrorCollector
) -> None:
    columns = [context.data.column(name) for name in rule.variables]
    for row_index in range(context.data.row_count):
        row_values = [column[row_index] for column in columns]
        if any(_is_missing(v) for v in row_values):
            continue

        numeric_values: list[float] = []
        for name, value in zip(rule.variables, row_values, strict=True):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuleEvaluationError(
                    f"Rule {rule.id!r}: {name!r} has non-numeric value {value!r} "
                    f"in row {row_index}."
                )
            numeric_values.append(value)

        total = sum(numeric_values)
        if abs(total - rule.target) > rule.tolerance:
            collector.add(
                ValidationResult(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        rule.message
                        or f"Sum of {rule.variables} should equal {rule.target} (got {total})."
                    ),
                    row_index=row_index,
                    variables=rule.variables,
                )
            )


def _execute_max_selections_rule(
    rule: MaxSelectionsRule, context: ValidationContext, collector: ErrorCollector
) -> None:
    values = context.data.column(rule.variable)
    for row_index, value in enumerate(values):
        selection = _as_selection(value, rule.id, rule.variable, row_index)
        if selection is None:
            continue
        if len(selection) > rule.max_selections:
            collector.add(
                ValidationResult(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        rule.message
                        or f"{rule.variable} has {len(selection)} selections, "
                        f"exceeding the maximum of {rule.max_selections}."
                    ),
                    row_index=row_index,
                    variables=(rule.variable,),
                )
            )


def _execute_exclusive_category_rule(
    rule: ExclusiveCategoryRule, context: ValidationContext, collector: ErrorCollector
) -> None:
    values = context.data.column(rule.variable)
    exclusive = set(rule.exclusive_codes)
    for row_index, value in enumerate(values):
        selection = _as_selection(value, rule.id, rule.variable, row_index)
        if selection is None:
            continue
        if (selection & exclusive) and (selection - exclusive):
            collector.add(
                ValidationResult(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        rule.message
                        or f"{rule.variable} combines an exclusive category with "
                        f"other selections."
                    ),
                    row_index=row_index,
                    variables=(rule.variable,),
                )
            )


# ---------------------------------------------------------------------------
# Built-in codebook-domain checks (the business-rules-KB "type validation"
# pattern) — not backed by any user-authored Rule object.
# ---------------------------------------------------------------------------


def _domain_result(
    question_id: str, check: str, message: str, row_index: int
) -> ValidationResult:
    return ValidationResult(
        rule_id=f"__domain__:{question_id}:{check}",
        severity=Severity.ERROR,
        message=message,
        row_index=row_index,
        variables=(question_id,),
    )


def _validate_codebook_domains(context: ValidationContext, collector: ErrorCollector) -> None:
    for question in context.codebook.questions:
        if isinstance(question, (DerivedVariable, GridQuestion, RankingQuestion)):
            # DerivedVariable: not yet computed (Cleaning Engine, Phase 7).
            # GridQuestion: not itself a data column; its rows are checked
            #   individually, since Codebook.questions already flattens them.
            # RankingQuestion: deferred alongside RankRule execution above.
            continue
        if question.id not in context.data.column_names:
            continue

        values = context.data.column(question.id)
        for row_index, value in enumerate(values):
            if _is_missing(value):
                if question.required:
                    collector.add(
                        _domain_result(
                            question.id,
                            "required",
                            f"{question.id} is required but missing.",
                            row_index,
                        )
                    )
                continue
            _check_domain(question, value, row_index, collector)


def _coerce_category_code(value: object) -> int | None:
    """Reconcile a data value against the ``int`` category-code contract.

    Category codes are declared as ``int`` (see
    :class:`~insightengine.core.codebook.Category`), but a numeric column
    containing *any* missing values commonly gets upcast to ``float64``
    by pandas — ``NaN`` requires a float dtype, so the whole column is
    promoted, and a value declared as the int ``1`` comes back from
    :class:`~insightengine.data.backends.pandas_backend.PandasBackend`
    as ``1.0``. Confirmed empirically while testing this exact check, not
    assumed. Returns the value as an ``int`` if it's already one, or a
    float with no fractional part; returns ``None`` (meaning "not a
    valid representation of any category code") for ``bool`` (never a
    legitimate code, even though ``bool`` is an ``int`` subclass) or any
    genuinely fractional float.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _check_domain(
    question: Question, value: object, row_index: int, collector: ErrorCollector
) -> None:
    if isinstance(question, SingleQuestion):
        valid_codes = {c.code for c in question.categories}
        code = _coerce_category_code(value)
        if code is None or code not in valid_codes:
            collector.add(
                _domain_result(
                    question.id,
                    "category",
                    f"{question.id} value {value!r} is not a valid category code.",
                    row_index,
                )
            )
        return

    if isinstance(question, MultiQuestion):
        if not isinstance(value, (list, tuple, set, frozenset)):
            collector.add(
                _domain_result(
                    question.id,
                    "type",
                    f"{question.id} value {value!r} is not a selection of category codes.",
                    row_index,
                )
            )
            return
        selected: set[object] = set()
        for item in value:
            selected.add(item)
        valid_codes = {c.code for c in question.categories}
        invalid = selected - valid_codes
        if invalid:
            collector.add(
                _domain_result(
                    question.id,
                    "category",
                    f"{question.id} contains invalid category codes: "
                    f"{sorted(invalid, key=repr)}.",
                    row_index,
                )
            )
        if question.max_selections is not None and len(selected) > question.max_selections:
            collector.add(
                _domain_result(
                    question.id,
                    "max_selections",
                    f"{question.id} has {len(selected)} selections, exceeding the "
                    f"declared maximum of {question.max_selections}.",
                    row_index,
                )
            )
        return

    if isinstance(question, NumericQuestion):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            collector.add(
                _domain_result(
                    question.id,
                    "type",
                    f"{question.id} value {value!r} is not numeric.",
                    row_index,
                )
            )
            return
        if question.min_value is not None and value < question.min_value:
            collector.add(
                _domain_result(
                    question.id,
                    "range",
                    f"{question.id} value {value!r} is below the minimum "
                    f"of {question.min_value}.",
                    row_index,
                )
            )
        if question.max_value is not None and value > question.max_value:
            collector.add(
                _domain_result(
                    question.id,
                    "range",
                    f"{question.id} value {value!r} is above the maximum "
                    f"of {question.max_value}.",
                    row_index,
                )
            )
        return

    if isinstance(question, TextQuestion):
        if not isinstance(value, str):
            collector.add(
                _domain_result(
                    question.id,
                    "type",
                    f"{question.id} value {value!r} is not text.",
                    row_index,
                )
            )
        elif question.max_length is not None and len(value) > question.max_length:
            collector.add(
                _domain_result(
                    question.id,
                    "max_length",
                    f"{question.id} text is {len(value)} characters, exceeding "
                    f"the maximum of {question.max_length}.",
                    row_index,
                )
            )
