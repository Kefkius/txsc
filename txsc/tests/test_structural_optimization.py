import unittest
from collections import namedtuple

from txsc.tests import BaseCompilerTest


EqualTest = namedtuple('EqualTest', ('expected', 'src1', 'src2'))

class BaseStructuralOptimizationTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(BaseStructuralOptimizationTest, cls)._options()
        # Optimization is not set to 2 because we don't want the constant
        # expressions to be evaluated.
        namespace.optimization = 1
        return namespace

    def _test(self, test):
        result1 = self._compile(test.src1)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result1, test.src1)
        self.assertEqual(test.expected, result1, errmsg)

        result2 = self._compile(test.src2)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result2, test.src2)
        self.assertEqual(test.expected, result2, errmsg)

        self.assertEqual(result1, result2)


class CompileTxScriptOptimizationsTest(BaseStructuralOptimizationTest):
    def test_logical_equivalence(self):
        for test in [
            EqualTest('10 LESSTHAN',    'assume a; a < 10;', 'assume a; 10 > a;'),
            EqualTest('10 GREATERTHAN', 'assume a; a > 10;', 'assume a; 10 < a;'),
        ]:
            self._test(test)

    def test_commutative_operations(self):
        for test in [
            EqualTest('5 ADD', 'assume a; a + 5;', 'assume a; 5 + a;'),
            EqualTest('5 MUL', 'assume a; a * 5;', 'assume a; 5 * a;'),
            EqualTest('5 BOOLAND', 'assume a; a and 5;', 'assume a; 5 and a;'),
            EqualTest('5 BOOLOR', 'assume a; a or 5;', 'assume a; 5 or a;'),
            EqualTest('5 AND', 'assume a; a & 5;', 'assume a; 5 & a;'),
            EqualTest('5 OR', 'assume a; a | 5;', 'assume a; 5 | a;'),
            EqualTest('5 XOR', 'assume a; a ^ 5;', 'assume a; 5 ^ a;'),
            EqualTest('5 EQUAL', 'assume a; a == 5;', 'assume a; 5 == a;'),
            EqualTest('5 EQUALVERIFY', 'assume a; verify a == 5;', 'assume a; verify 5 == a;'),
        ]:
            self._test(test)

    def test_expressions_with_commutative_operations(self):
        for test in [
            EqualTest('10 LESSTHAN 2 5 LESSTHAN BOOLAND', 'assume a; 2 < 5 and a < 10;', 'assume a; a < 10 and 2 < 5;'),
        ]:
            self._test(test)

    def test_commutative_expressions(self):
        for expected, src in [
            ('2 3 ADD ADD', 'assume a; 2 + a + 3;'),
        ]:
            result = self._compile(src)
            self.assertEqual(expected, result)


class AggressiveOptimizationsTest(BaseStructuralOptimizationTest):
    @classmethod
    def _options(cls):
        namespace = super(AggressiveOptimizationsTest, cls)._options()
        # Optimization level that causes constant expressions to be evaluated.
        namespace.optimization = 2
        return namespace

    def test_negative_number(self):
        for expected, src in [
            ('0x01 0x85', '-5;'),
        ]:
            result = self._compile(src)
            self.assertEqual(expected, result)

    def test_constant_arithmetic_expression(self):
        for expected, src in [
            ('5', '6 - 1;'),
        ]:
            result = self._compile(src)
            self.assertEqual(expected, result)

    def test_function_calls(self):
        for expected, src in [
            ('5', 'func int addVars(a, b) {return a + b;} addVars(2, 3);'),
            ('12', 'func int addVars(a, b) {return a + b;} addVars(addVars(2, 3), 7);'),
        ]:
            result = self._compile(src)
            self.assertEqual(expected, result)
