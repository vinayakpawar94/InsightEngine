"""A restricted expression language for rule ``when:`` conditions.

**Security design, stated up front because it's the entire point of this
module:** this evaluator never calls Python's ``eval()``, ``exec()``, or
``compile()``-to-bytecode. An expression is parsed to an AST
(:func:`ast.parse`, ``mode="eval"``), that AST is walked and validated
against an explicit **whitelist** of node types and operators (default
deny — anything not explicitly reasoned about here is rejected, not
anything explicitly blacklisted), and only then is it evaluated, by a
hand-written recursive-descent interpreter (:func:`_eval_node`) that
never touches Python's real ``eval``/``compile`` machinery. This is
deliberate defense in depth: even if the whitelist had a bug and let
through a node type nobody intended, there is no bytecode-compilation
step where that node could still do something with the full authority
of the Python interpreter — ``_eval_node`` simply doesn't know how to
execute anything it wasn't explicitly written to handle, and raises
instead.

**What's allowed:** boolean combinators (``and``/``or``/``not``),
comparisons (``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``,
``not in``), arithmetic (``+``, ``-``, ``*``, ``/``, ``%``, unary
``-``/``+``), variable references, literals (numbers, strings,
booleans, ``None``), list/tuple/set literals (for the right-hand side of
``in``), and calls to an explicit, small, caller-extendable whitelist of
functions (only ``abs`` ships in this phase — see
:func:`default_functions`).

**What's never allowed, regardless of framing:** attribute access
(``x.__class__``, blocks the most common sandbox-escape vector
outright), subscripting (``x[0]``, ``__builtins__['exec']``-style
tricks), function calls to anything not in the whitelist, lambdas,
comprehensions, the walrus operator, f-strings, starred arguments, and
keyword arguments to whitelisted functions (kept simple; none of the
built-in functions need them).
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from insightengine.core.exceptions import (
    RuleEvaluationError,
    RuleParseError,
    UnknownVariableError,
    UnsafeExpressionError,
)

_ALLOWED_BOOL_OPS: tuple[type[ast.boolop], ...] = (ast.And, ast.Or)
_ALLOWED_UNARY_OPS: tuple[type[ast.unaryop], ...] = (ast.Not, ast.USub, ast.UAdd)
_ALLOWED_BIN_OPS: tuple[type[ast.operator], ...] = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
)
_ALLOWED_COMPARE_OPS: tuple[type[ast.cmpop], ...] = (
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)
_ALLOWED_CONSTANT_TYPES: tuple[type[object], ...] = (int, float, str, bool)

_ALLOWED_NODE_TYPES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Compare,
    ast.Name,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Call,
    ast.Load,
    # Operator/comparator marker node types themselves. ast.iter_child_nodes
    # visits e.g. the ast.Lt() object inside an ast.Compare, not just the
    # Compare node — omitting these here would reject every comparison and
    # boolean expression outright before the operator-specific checks below
    # ever ran. (Caught by this module's own functional test suite, which
    # is exactly why those tests exist independent of the adversarial ones.)
    *_ALLOWED_BOOL_OPS,
    *_ALLOWED_UNARY_OPS,
    *_ALLOWED_BIN_OPS,
    *_ALLOWED_COMPARE_OPS,
)

_MAX_NODE_COUNT = 200
"""A hard cap on how many AST nodes a single expression may contain.

A legitimate business rule (``AGE < 18 or AGE > 99``, a sum-to-100
check, a rank-count comparison) needs a handful of nodes. This exists
purely as a cheap, deterministic denial-of-service guard against a
pathologically large expression consuming excessive CPU/memory during
validation or evaluation — independent of, and in addition to, the
``RecursionError`` guards around parsing and evaluation below.
"""


def default_functions() -> dict[str, Callable[..., object]]:
    """The built-in function whitelist available to every expression
    unless a caller supplies its own via :func:`compile_expression`.

    Deliberately minimal in this phase: ``abs`` needs no knowledge of
    survey/execution context and is unambiguously safe. Functions like
    ``count()``/``sum()`` over a multi-response question's selected
    categories are *not* added here — their correct signature depends on
    what "the current case's data" looks like to a rule, which is
    Phase 6's (Validation Execution) concern, not this module's. Adding
    them now would mean guessing an interface before the thing that
    needs it exists.
    """
    return {"abs": abs}


class CompiledExpression:
    """A parsed, validated, safe-to-evaluate ``when:`` expression.

    Not constructed directly — obtained from :func:`compile_expression`,
    which is the only place the safety validation in this module runs.
    """

    def __init__(
        self,
        source: str,
        tree: ast.Expression,
        functions: Mapping[str, Callable[..., object]],
    ) -> None:
        self._source = source
        self._tree = tree
        self._functions = functions

    @property
    def source(self) -> str:
        """The original expression text this was compiled from."""
        return self._source

    def evaluate(self, variables: Mapping[str, object]) -> object:
        """Evaluate this expression against a variable namespace.

        Args:
            variables: Maps variable names referenced in the expression
                to their current values.

        Raises:
            UnknownVariableError: If the expression references a name
                not present in ``variables``.
            RuleEvaluationError: If evaluation fails for a data/type
                reason (arithmetic on a non-number, division by zero,
                comparing incompatible types) — the expression itself
                was already confirmed safe at compile time; this is a
                runtime data problem, not a security one.
        """
        try:
            return _eval_node(self._tree.body, variables, self._functions)
        except RecursionError as exc:  # pragma: no cover
            # Defense-in-depth, not a normally-reachable path: anything deep
            # enough to blow this function's Python-level recursion stack
            # would already have been rejected earlier, either by
            # _MAX_NODE_COUNT in compile_expression or by CPython's own
            # parser (verified empirically: CPython converts pathological
            # nesting into a SyntaxError during ast.parse, before a tree
            # this deep ever reaches this method). Kept for other Python
            # implementations / future CPython changes, not because it's
            # exercised in practice.
            raise RuleEvaluationError(
                f"Expression {self._source!r} is too deeply nested to evaluate."
            ) from exc

    def __repr__(self) -> str:
        return f"CompiledExpression({self._source!r})"


def compile_expression(
    source: str, *, functions: Mapping[str, Callable[..., object]] | None = None
) -> CompiledExpression:
    """Parse and safety-validate a ``when:`` expression.

    Args:
        source: The expression text, e.g. ``"AGE < 18 or AGE > 99"``.
        functions: Additional whitelisted functions beyond
            :func:`default_functions`, merged in (caller-supplied names
            take precedence on collision). Passed explicitly by whatever
            later phase needs to extend the whitelist — never inferred
            or auto-discovered, since an auto-discovery mechanism for
            "callable things" is itself an injection risk.

    Raises:
        RuleParseError: If ``source`` is not valid Python expression
            syntax, or is too deeply nested to parse.
        UnsafeExpressionError: If ``source`` parses but uses any
            construct outside the whitelist described in this module's
            docstring.
    """
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise RuleParseError(f"Expression {source!r} is not valid syntax: {exc}") from exc
    except RecursionError as exc:  # pragma: no cover
        # Verified empirically: CPython's PEG parser converts pathological
        # nesting depth into a SyntaxError ("too many nested parentheses"),
        # not a Python-level RecursionError - so this branch is not
        # reachable through ast.parse on current CPython. Kept for other
        # Python implementations or parser changes, not because it fires
        # in practice; see test_deeply_nested_parentheses_raises_rule_parse_error,
        # which confirms the SyntaxError path is what actually triggers today.
        raise RuleParseError(f"Expression {source!r} is too deeply nested to parse.") from exc

    resolved_functions = default_functions()
    if functions:
        resolved_functions.update(functions)
    allowed_function_names = frozenset(resolved_functions)

    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > _MAX_NODE_COUNT:
        raise RuleParseError(
            f"Expression {source!r} has {node_count} AST nodes, exceeding the "
            f"limit of {_MAX_NODE_COUNT}."
        )

    try:
        _validate_node(tree, source, allowed_function_names)
    except RecursionError as exc:  # pragma: no cover
        # Same reasoning as the two RecursionError guards above: a tree
        # deep enough to blow this recursive validator's Python stack would
        # already have been rejected by CPython's own parser first.
        raise RuleParseError(f"Expression {source!r} is too deeply nested to validate.") from exc

    return CompiledExpression(source=source, tree=tree, functions=resolved_functions)


# ---------------------------------------------------------------------------
# Static validation: the whitelist enforcement itself.
# ---------------------------------------------------------------------------


def _validate_node(node: ast.AST, source: str, allowed_function_names: frozenset[str]) -> None:
    if not isinstance(node, _ALLOWED_NODE_TYPES):
        raise UnsafeExpressionError(
            f"Expression {source!r} uses a disallowed construct: {type(node).__name__}."
        )

    if isinstance(node, ast.BoolOp) and not isinstance(node.op, _ALLOWED_BOOL_OPS):  # pragma: no cover
        # Unreachable in practice: Python's ast module defines exactly two
        # boolop subclasses, And and Or, and both are already whitelisted -
        # there is no third case ast.parse can ever produce here. Kept for
        # symmetry with the UnaryOp/BinOp/Compare operator checks below,
        # which do guard against real, reachable alternatives.
        raise UnsafeExpressionError(
            f"Expression {source!r} uses a disallowed boolean operator: "
            f"{type(node.op).__name__}."
        )
    if isinstance(node, ast.UnaryOp) and not isinstance(node.op, _ALLOWED_UNARY_OPS):
        raise UnsafeExpressionError(
            f"Expression {source!r} uses a disallowed unary operator: {type(node.op).__name__}."
        )
    if isinstance(node, ast.BinOp) and not isinstance(node.op, _ALLOWED_BIN_OPS):
        raise UnsafeExpressionError(
            f"Expression {source!r} uses a disallowed arithmetic operator: "
            f"{type(node.op).__name__}."
        )
    if isinstance(node, ast.Compare):
        for op in node.ops:
            if not isinstance(op, _ALLOWED_COMPARE_OPS):
                raise UnsafeExpressionError(
                    f"Expression {source!r} uses a disallowed comparison operator: "
                    f"{type(op).__name__}."
                )
    if isinstance(node, ast.Constant) and not isinstance(node.value, _ALLOWED_CONSTANT_TYPES):
        if node.value is not None:
            raise UnsafeExpressionError(
                f"Expression {source!r} contains an unsupported literal type: "
                f"{type(node.value).__name__}."
            )
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError(
                f"Expression {source!r} calls something that isn't a plain function name."
            )
        if node.func.id not in allowed_function_names:
            raise UnsafeExpressionError(
                f"Expression {source!r} calls unknown/disallowed function {node.func.id!r}."
            )
        if node.keywords:
            raise UnsafeExpressionError(
                f"Expression {source!r} uses keyword arguments, which are not supported."
            )
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise UnsafeExpressionError(
                    f"Expression {source!r} uses starred arguments, which are not supported."
                )

    for child in ast.iter_child_nodes(node):
        _validate_node(child, source, allowed_function_names)


# ---------------------------------------------------------------------------
# Evaluation: the hand-written interpreter over an already-validated tree.
# ---------------------------------------------------------------------------


def _truthy(value: object) -> bool:
    return bool(value)


def _as_number(value: object, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuleEvaluationError(
            f"{context} requires a number, got {type(value).__name__} ({value!r})."
        )
    return value


def _apply_binop(op: ast.operator, left: object, right: object) -> object:
    op_name = type(op).__name__
    left_num = _as_number(left, f"the left operand of {op_name}")
    right_num = _as_number(right, f"the right operand of {op_name}")

    if isinstance(op, ast.Add):
        return left_num + right_num
    if isinstance(op, ast.Sub):
        return left_num - right_num
    if isinstance(op, ast.Mult):
        return left_num * right_num
    if isinstance(op, ast.Div):
        if right_num == 0:
            raise RuleEvaluationError("Division by zero in expression.")
        return left_num / right_num
    if isinstance(op, ast.Mod):
        if right_num == 0:
            raise RuleEvaluationError("Modulo by zero in expression.")
        return left_num % right_num

    raise UnsafeExpressionError(  # pragma: no cover - unreachable if _validate_node ran first
        f"Unsupported binary operator {op_name} (should have been rejected at compile time)."
    )


def _apply_compare(op: ast.cmpop, left: object, right: object) -> bool:
    try:
        if isinstance(op, ast.Eq):
            return bool(left == right)
        if isinstance(op, ast.NotEq):
            return bool(left != right)
        if isinstance(op, ast.Lt):
            return bool(left < right)  # type: ignore[operator]
        if isinstance(op, ast.LtE):
            return bool(left <= right)  # type: ignore[operator]
        if isinstance(op, ast.Gt):
            return bool(left > right)  # type: ignore[operator]
        if isinstance(op, ast.GtE):
            return bool(left >= right)  # type: ignore[operator]
        if isinstance(op, ast.In):
            return bool(left in right)  # type: ignore[operator]
        if isinstance(op, ast.NotIn):
            return bool(left not in right)  # type: ignore[operator]
    except TypeError as exc:
        raise RuleEvaluationError(
            f"Cannot compare {type(left).__name__} and {type(right).__name__}: {exc}"
        ) from exc

    raise UnsafeExpressionError(  # pragma: no cover - unreachable if _validate_node ran first
        f"Unsupported comparison operator {type(op).__name__} (should have been rejected "
        f"at compile time)."
    )


def _eval_compare(
    node: ast.Compare,
    variables: Mapping[str, object],
    functions: Mapping[str, Callable[..., object]],
) -> bool:
    left = _eval_node(node.left, variables, functions)
    for op, comparator_node in zip(node.ops, node.comparators, strict=True):
        right = _eval_node(comparator_node, variables, functions)
        if not _apply_compare(op, left, right):
            return False
        left = right
    return True


def _eval_node(
    node: ast.AST,
    variables: Mapping[str, object],
    functions: Mapping[str, Callable[..., object]],
) -> object:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        try:
            return variables[node.id]
        except KeyError as exc:
            raise UnknownVariableError(
                f"Unknown variable {node.id!r} referenced in expression."
            ) from exc

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: object = True
            for value_node in node.values:
                result = _eval_node(value_node, variables, functions)
                if not _truthy(result):
                    return result
            return result
        result = False
        for value_node in node.values:
            result = _eval_node(value_node, variables, functions)
            if _truthy(result):
                return result
        return result

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables, functions)
        if isinstance(node.op, ast.Not):
            return not _truthy(operand)
        operand_num = _as_number(operand, "the operand of a unary +/-")
        if isinstance(node.op, ast.USub):
            return -operand_num
        return +operand_num

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables, functions)
        right = _eval_node(node.right, variables, functions)
        return _apply_binop(node.op, left, right)

    if isinstance(node, ast.Compare):
        return _eval_compare(node, variables, functions)

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_eval_node(elt, variables, functions) for elt in node.elts]
        if isinstance(node, ast.List):
            return values
        if isinstance(node, ast.Tuple):
            return tuple(values)
        return set(values)

    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)  # guaranteed by _validate_node
        func = functions[node.func.id]
        args = [_eval_node(arg, variables, functions) for arg in node.args]
        return func(*args)

    raise UnsafeExpressionError(  # pragma: no cover - unreachable if _validate_node ran first
        f"Cannot evaluate node type {type(node).__name__} "
        f"(this should have been rejected at compile time)."
    )
