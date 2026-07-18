"""The complete exception hierarchy for the insightengine framework.

Defined once, here, in Foundation — rather than scattered per-subsystem —
so that every later phase (Metadata Engine, Data Engine, Rule Engine, ...)
imports from one stable location instead of inventing its own error types
as it goes. Leaf exceptions for subsystems that don't exist yet (e.g.
:class:`RuleParseError`) are included now so that this module never needs
a backwards-incompatible restructuring once those subsystems are built;
each is documented with the phase that will raise it.

All exceptions carry a plain, human-readable message. None of them are
control-flow signals — every exception here represents a genuine failure
that should stop the current operation.
"""

from __future__ import annotations


class InsightEngineError(Exception):
    """Base class for every exception raised by the insightengine framework.

    Catching this (rather than ``Exception``) is the correct way for a
    caller to mean "any error this framework can raise, as opposed to a
    bug in my own code or a third-party library's error."
    """


class ConfigurationError(InsightEngineError):
    """Raised when application configuration is missing, malformed, or invalid."""


class InvalidSettingsError(ConfigurationError):
    """Raised when a settings file fails schema validation.

    Raised by :func:`insightengine.core.config.load_config` (this phase).
    """


class CodebookError(InsightEngineError):
    """Base class for errors in the metadata/codebook model.

    Raised by the Core Domain Models phase (Phase 2) and the Metadata
    Engine phase (Phase 4).
    """


class DuplicateQuestionIdError(CodebookError):
    """Raised when two questions in the same codebook share an id. (Phase 2)"""


class CircularDependencyError(CodebookError):
    """Raised when derived-variable dependencies form a cycle. (Phase 2)"""


class UnknownVariableError(CodebookError):
    """Raised when a rule or derivation references a variable id that
    does not exist in the codebook. (Phase 2 / Phase 5)
    """


class InvalidQuestionDefinitionError(CodebookError):
    """Raised when a single :class:`~insightengine.core.codebook.Question`
    is structurally invalid on its own terms — e.g. a categorical question
    with zero categories, duplicate category codes within one question, or
    a ranking question whose rank depth exceeds its item count. Distinct
    from :class:`DuplicateQuestionIdError`/:class:`CircularDependencyError`,
    which are properties of a *collection* of questions (the
    :class:`~insightengine.core.codebook.Codebook`), not of one question
    in isolation. (Phase 2)
    """


class MetadataParseError(CodebookError):
    """Raised when a metadata source (a native YAML codebook file, in
    Phase 4) is structurally invalid before it can even become a
    :class:`~insightengine.core.codebook.Codebook` — a missing required
    field, an unrecognized question ``type``, malformed YAML — or fails
    an authoring-quality check that isn't a hard domain-model invariant
    but is almost always a mistake, such as two categories in the same
    question sharing an identical label under different codes. (Phase 4)
    """


class DataBackendError(InsightEngineError):
    """Base class for errors from the Data Engine. (Phase 3)"""


class UnsupportedFormatError(DataBackendError):
    """Raised when asked to load a file format with no registered backend. (Phase 3)"""


class DataLoadError(DataBackendError):
    """Raised when a recognized format fails to load (corrupt file, bad
    encoding, schema mismatch). (Phase 3)
    """


class UnknownColumnError(DataBackendError):
    """Raised when code asks a :class:`~insightengine.data.base.DataHandle`
    for a column name it doesn't have. (Phase 3)
    """


class RuleEngineError(InsightEngineError):
    """Base class for errors from the Rule Engine. (Phase 5)"""


class RuleParseError(RuleEngineError):
    """Raised when a rule definition fails schema or grammar validation. (Phase 5)"""


class UnsafeExpressionError(RuleEngineError):
    """Raised when a ``when:`` expression contains a construct the
    restricted evaluator refuses to execute (attribute access, calls to
    non-whitelisted functions, imports, etc.). This is a security
    boundary, not a convenience check — see Phase 5's acceptance criteria
    in the implementation roadmap. This is a **static** check: it fires
    while validating an expression's parsed structure, before any
    evaluation against real data is attempted. Compare
    :class:`RuleEvaluationError`, which fires *during* evaluation of an
    already-validated, safe expression.
    """


class RuleEvaluationError(RuleEngineError):
    """Raised when a ``when:`` expression is syntactically valid and uses
    only whitelisted constructs (i.e. it already passed the
    :class:`UnsafeExpressionError` check), but evaluating it against
    actual variable values fails for a data/type reason — arithmetic on a
    non-numeric value, division by zero, comparing incompatible types.
    Distinct from :class:`UnsafeExpressionError`: this is a runtime data
    problem, not a security/safety problem. (Phase 5)
    """


class InvalidRuleDefinitionError(RuleEngineError):
    """Raised when a single rule (one
    :class:`~insightengine.rules.dsl.Rule` instance) is structurally
    invalid on its own terms — e.g. a ``SumEqualsRule`` with fewer than
    two variables, or a ``RankRule`` with an empty variable list. Mirrors
    :class:`~insightengine.core.exceptions.InvalidQuestionDefinitionError`'s
    role for :class:`~insightengine.core.codebook.Question`: a single
    object's own internal validity, not a collection-level property.
    (Phase 5)
    """


class PluginError(InsightEngineError):
    """Base class for plugin registry errors. (This phase)"""


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin name has no registered implementation."""


class DuplicatePluginError(PluginError):
    """Raised when attempting to register a plugin name that is already registered."""


class ExecutionError(InsightEngineError):
    """Base class for errors from the Execution Pipeline. (Phase 8)"""


class ManifestError(ExecutionError):
    """Raised when a run manifest cannot be read, is malformed, or a
    resume was requested against a run directory with no manifest at
    all. (Phase 8)
    """


class CleaningError(InsightEngineError):
    """Base class for errors from the Cleaning Engine. (Phase 7)"""


class TransformationError(CleaningError):
    """Raised when a :class:`~insightengine.cleaning.transformer.Transformer`
    cannot apply itself to the data it was given — a malformed
    multi-response indicator value, a recode referencing an unknown
    variable, a derived variable's expression failing against a specific
    row's actual data, etc. (Phase 7)
    """
