"""The structured result of a single rule violation."""

from __future__ import annotations

from dataclasses import dataclass

from insightengine.core.types import Severity


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """One rule violation found while validating a dataset.

    Args:
        rule_id: The id of the rule (or, for built-in codebook-domain
            checks that aren't backed by a user-authored
            :class:`~insightengine.rules.dsl.Rule` at all, a synthetic id
            of the form ``"__domain__:<question_id>:<check>"`` — see
            :mod:`insightengine.validation.executor`) that produced this
            result.
        severity: How serious this violation is.
        message: A human-readable description of what went wrong.
        row_index: The zero-based physical row index in the dataset this
            violation occurred on. Not a respondent/case id — the
            validation layer has no concept of which column (if any) is
            a case identifier, since that's survey-specific and nothing
            in the Codebook model designates one. Callers who need a
            real case id should look it up themselves via ``row_index``
            against whichever column they know holds it.
        variables: The variable(s) this violation concerns. May be empty
            for rules whose condition spans variables this layer can't
            enumerate without walking the expression's internals (see
            :mod:`insightengine.rules.evaluator` — ``CompiledExpression``
            deliberately doesn't expose which names it references).
    """

    rule_id: str
    severity: Severity
    message: str
    row_index: int
    variables: tuple[str, ...] = ()
