"""Unit tests for insightengine.rules.evaluator.

Organized into two tiers, deliberately:

* **Functional tests** — the evaluator computes the right answer for
  legitimate expressions.
* **Adversarial security tests** — every construct this module's
  docstring says is blocked is actually tested with a real malicious-
  shaped payload, not just asserted about in prose. This is the
  acceptance criterion for the whole phase: a malicious ``when:`` string
  must be rejected, not executed.
"""

from __future__ import annotations

import pytest

from insightengine.core.exceptions import (
    RuleEvaluationError,
    RuleParseError,
    UnknownVariableError,
    UnsafeExpressionError,
)
from insightengine.rules.evaluator import compile_expression


class TestFunctionalArithmeticAndComparison:
    def test_simple_comparison_true(self) -> None:
        expr = compile_expression("AGE < 18")
        assert expr.evaluate({"AGE": 10}) is True

    def test_simple_comparison_false(self) -> None:
        expr = compile_expression("AGE < 18")
        assert expr.evaluate({"AGE": 25}) is False

    def test_or_condition(self) -> None:
        expr = compile_expression("AGE < 18 or AGE > 99")
        assert expr.evaluate({"AGE": 5}) is True
        assert expr.evaluate({"AGE": 150}) is True
        assert expr.evaluate({"AGE": 40}) is False

    def test_and_condition(self) -> None:
        expr = compile_expression("AGE >= 18 and AGE <= 65")
        assert expr.evaluate({"AGE": 30}) is True
        assert expr.evaluate({"AGE": 10}) is False

    def test_not_operator(self) -> None:
        expr = compile_expression("not (AGE < 18)")
        assert expr.evaluate({"AGE": 30}) is True
        assert expr.evaluate({"AGE": 10}) is False

    def test_equality_string(self) -> None:
        expr = compile_expression("Q1 == 'Yes'")
        assert expr.evaluate({"Q1": "Yes"}) is True
        assert expr.evaluate({"Q1": "No"}) is False

    def test_not_equal(self) -> None:
        expr = compile_expression("Q1 != 'Yes'")
        assert expr.evaluate({"Q1": "No"}) is True

    def test_chained_comparison(self) -> None:
        expr = compile_expression("1 <= RANK <= 3")
        assert expr.evaluate({"RANK": 2}) is True
        assert expr.evaluate({"RANK": 5}) is False

    def test_arithmetic_sum(self) -> None:
        expr = compile_expression("S9_1 + S9_2 == 100")
        assert expr.evaluate({"S9_1": 40, "S9_2": 60}) is True
        assert expr.evaluate({"S9_1": 40, "S9_2": 50}) is False

    def test_arithmetic_all_operators(self) -> None:
        assert compile_expression("2 + 3").evaluate({}) == 5
        assert compile_expression("5 - 2").evaluate({}) == 3
        assert compile_expression("4 * 2").evaluate({}) == 8
        assert compile_expression("10 / 4").evaluate({}) == 2.5
        assert compile_expression("10 % 3").evaluate({}) == 1

    def test_unary_minus_and_plus(self) -> None:
        assert compile_expression("-AGE").evaluate({"AGE": 5}) == -5
        assert compile_expression("+AGE").evaluate({"AGE": 5}) == 5

    def test_in_operator_with_list(self) -> None:
        expr = compile_expression("Q1 in [1, 2, 3]")
        assert expr.evaluate({"Q1": 2}) is True
        assert expr.evaluate({"Q1": 9}) is False

    def test_not_in_operator(self) -> None:
        expr = compile_expression("Q1 not in [1, 2, 3]")
        assert expr.evaluate({"Q1": 9}) is True

    def test_in_operator_with_set_and_tuple_literals(self) -> None:
        assert compile_expression("Q1 in {1, 2, 3}").evaluate({"Q1": 2}) is True
        assert compile_expression("Q1 in (1, 2, 3)").evaluate({"Q1": 2}) is True

    def test_boolean_literal(self) -> None:
        assert compile_expression("True").evaluate({}) is True
        assert compile_expression("False").evaluate({}) is False

    def test_none_literal(self) -> None:
        assert compile_expression("Q1 == None").evaluate({"Q1": None}) is True

    def test_abs_function(self) -> None:
        expr = compile_expression("abs(A - B) < 5")
        assert expr.evaluate({"A": 10, "B": 8}) is True
        assert expr.evaluate({"A": 10, "B": 1}) is False

    def test_short_circuit_and_does_not_evaluate_second_operand(self) -> None:
        # If short-circuiting weren't implemented, this would raise
        # UnknownVariableError trying to look up UNDEFINED.
        expr = compile_expression("False and UNDEFINED == 1")
        assert expr.evaluate({}) is False

    def test_short_circuit_or_does_not_evaluate_second_operand(self) -> None:
        expr = compile_expression("True or UNDEFINED == 1")
        assert expr.evaluate({}) is True


class TestRuntimeEvaluationErrors:
    def test_unknown_variable_raises(self) -> None:
        expr = compile_expression("AGE < 18")
        with pytest.raises(UnknownVariableError, match="AGE"):
            expr.evaluate({})

    def test_arithmetic_on_non_number_raises_rule_evaluation_error(self) -> None:
        expr = compile_expression("AGE + 1")
        with pytest.raises(RuleEvaluationError, match="requires a number"):
            expr.evaluate({"AGE": "not a number"})

    def test_division_by_zero_raises(self) -> None:
        expr = compile_expression("A / B")
        with pytest.raises(RuleEvaluationError, match="Division by zero"):
            expr.evaluate({"A": 1, "B": 0})

    def test_modulo_by_zero_raises(self) -> None:
        expr = compile_expression("A % B")
        with pytest.raises(RuleEvaluationError, match="Modulo by zero"):
            expr.evaluate({"A": 1, "B": 0})

    def test_incompatible_comparison_raises(self) -> None:
        expr = compile_expression("A < B")
        with pytest.raises(RuleEvaluationError, match="Cannot compare"):
            expr.evaluate({"A": 1, "B": "x"})

    def test_bool_is_rejected_as_a_number_for_arithmetic(self) -> None:
        # isinstance(True, int) is True in Python; explicitly rejecting
        # bool for arithmetic prevents "AGE + True" silently meaning
        # "AGE + 1" in a way nobody intended when authoring a rule.
        expr = compile_expression("AGE + FLAG")
        with pytest.raises(RuleEvaluationError, match="requires a number"):
            expr.evaluate({"AGE": 10, "FLAG": True})


class TestParseErrors:
    def test_invalid_syntax_raises_rule_parse_error(self) -> None:
        with pytest.raises(RuleParseError, match="not valid syntax"):
            compile_expression("AGE < ")

    def test_empty_string_raises_rule_parse_error(self) -> None:
        with pytest.raises(RuleParseError):
            compile_expression("")


class TestAdversarialSecurityRejections:
    """Every one of these is a real, shaped attempt at sandbox escape or
    disallowed behavior — not a hypothetical description of one.
    """

    def test_dunder_class_attribute_access_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE.__class__")

    def test_classic_sandbox_escape_via_subclasses_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression(
                "AGE.__class__.__mro__[1].__subclasses__()"
            )

    def test_builtins_attribute_access_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE.__class__.__init__.__globals__")

    def test_subscript_access_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE[0]")

    def test_call_to_arbitrary_name_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="unknown/disallowed function"):
            compile_expression("eval('1')")

    def test_call_to_exec_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("exec('pass')")

    def test_call_to_open_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("open('/etc/passwd')")

    def test_call_to_import_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("__import__('os')")

    def test_lambda_rejected(self) -> None:
        # Also exercises the "Call target must be a plain Name" check:
        # here the Call's .func is an ast.Lambda, not an ast.Name, so this
        # is rejected before ever reaching a Lambda-specific check.
        with pytest.raises(UnsafeExpressionError):
            compile_expression("(lambda: 1)()")

    def test_list_comprehension_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("[x for x in [1,2,3]]")

    def test_generator_expression_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("sum(x for x in [1,2,3])")

    def test_dict_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("{'a': 1}")

    def test_walrus_operator_rejected(self) -> None:
        with pytest.raises((UnsafeExpressionError, RuleParseError)):
            compile_expression("(x := 5)")

    def test_fstring_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("f'{AGE}'")

    def test_starred_argument_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("abs(*[1])")

    def test_keyword_argument_rejected(self) -> None:
        # abs() doesn't take kwargs anyway, but the rejection must happen
        # at the "this call uses keyword arguments" check, not leak
        # through to a TypeError from the underlying function.
        with pytest.raises(UnsafeExpressionError, match="keyword arguments"):
            compile_expression("abs(x=AGE)")

    def test_ternary_conditional_expression_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("1 if AGE > 18 else 0")

    def test_bitwise_operators_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE & 1")
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE | 1")
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE ^ 1")
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE << 1")

    def test_power_operator_rejected(self) -> None:
        # Deliberately excluded from the arithmetic whitelist: no
        # legitimate survey rule needs exponentiation, and it's a classic
        # DoS vector (e.g. 9**9**9) if left in.
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE ** 2")

    def test_floor_division_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE // 2")

    def test_matrix_multiplication_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE @ AGE")

    def test_unary_invert_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="unary operator"):
            compile_expression("~AGE")

    def test_right_shift_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE >> 1")

    def test_is_operator_rejected(self) -> None:
        # `is`/`is not` aren't in the whitelist at all - not because
        # identity comparison is dangerous by itself, but because this
        # module's whole design principle is default-deny: nothing gets
        # in without an explicit reason, and no rule pattern in the
        # business-rules catalogue needs identity comparison.
        with pytest.raises(UnsafeExpressionError, match="comparison operator"):
            compile_expression("Q1 is None")

    def test_is_not_operator_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="comparison operator"):
            compile_expression("Q1 is not None")

    def test_complex_number_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="unsupported literal type"):
            compile_expression("1j")

    def test_bytes_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="unsupported literal type"):
            compile_expression("b'x'")

    def test_ellipsis_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="unsupported literal type"):
            compile_expression("...")

    def test_yield_rejected(self) -> None:
        with pytest.raises((RuleParseError, UnsafeExpressionError)):
            compile_expression("(yield 1)")

    def test_nested_disallowed_construct_inside_allowed_structure_still_rejected(
        self,
    ) -> None:
        # The dangerous construct is buried inside an otherwise-legal
        # boolean expression - the recursive validator must still catch it.
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE < 18 or AGE.__class__ == int")

    def test_disallowed_construct_inside_function_call_argument_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("abs(AGE.__class__)")

    def test_disallowed_construct_inside_list_literal_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            compile_expression("AGE in [AGE.__class__]")


class TestDenialOfServiceGuards:
    def test_excessively_long_expression_raises_rule_parse_error(self) -> None:
        # A single expression built from thousands of "1 +" terms is
        # syntactically valid Python but has no legitimate business-rule
        # use - the explicit node-count cap should reject it before
        # attempting to validate or evaluate the whole tree.
        huge_expression = "1" + " + 1" * 5000
        with pytest.raises(RuleParseError, match="AST nodes"):
            compile_expression(huge_expression)

    def test_deeply_nested_parentheses_raises_rule_parse_error(self) -> None:
        deeply_nested = "(" * 3000 + "1" + ")" * 3000
        with pytest.raises(RuleParseError):
            compile_expression(deeply_nested)


class TestCustomFunctionWhitelist:
    def test_caller_can_extend_the_function_whitelist(self) -> None:
        expr = compile_expression(
            "double(AGE) > 20", functions={"double": lambda x: x * 2}
        )
        assert expr.evaluate({"AGE": 15}) is True

    def test_caller_supplied_function_does_not_disable_default_whitelist_check(
        self,
    ) -> None:
        # Supplying a custom function must not accidentally widen the
        # whitelist to allow arbitrary calls - only the explicitly named
        # additional function (plus the defaults) should be callable.
        with pytest.raises(UnsafeExpressionError, match="unknown/disallowed function"):
            compile_expression("triple(AGE)", functions={"double": lambda x: x * 2})

    def test_abs_still_available_when_extra_functions_supplied(self) -> None:
        expr = compile_expression(
            "abs(AGE) > 5", functions={"double": lambda x: x * 2}
        )
        assert expr.evaluate({"AGE": -10}) is True


class TestCompiledExpressionRepr:
    def test_repr_includes_source(self) -> None:
        expr = compile_expression("AGE < 18")
        assert "AGE < 18" in repr(expr)

    def test_source_property(self) -> None:
        expr = compile_expression("AGE < 18")
        assert expr.source == "AGE < 18"
