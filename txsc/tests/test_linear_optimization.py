import unittest

from txsc.symbols import SymbolTable
from txsc.ir.instructions import LInstructions
from txsc.ir.linear_optimizer import LinearOptimizer
import txsc.ir.linear_nodes as types

class BaseOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.optimizer = LinearOptimizer
        self.symbol_table = SymbolTable()

    def _do_test(self, expected, ops_list):
        script = LInstructions(ops_list)
        original = str(script)
        self.optimizer(self.symbol_table).optimize(script)
        expected = str(expected.split(' '))
        self.assertEqual(expected, str(script), '%s != %s (original: %s)' % (expected, str(script), original))

class OptimizationTest(BaseOptimizationTest):
    def setUp(self):
        super(OptimizationTest, self).setUp()
        self.symbol_table.add_stack_assumptions(['testItem'])

    def test_merge_op_and_verify(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY', script)

        script = [types.Five(), types.Five(), types.NumEqual(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_NUMEQUALVERIFY', script)

    def test_alt_stack_ops(self):
        for script in [
            [types.Five(), types.ToAltStack(), types.FromAltStack()],
            [types.Five(), types.FromAltStack(), types.ToAltStack()],
        ]:
            self._do_test('OP_5', script)

    def test_stack_ops(self):
        script = [types.Five(), types.One(), types.Pick()]
        self._do_test('OP_5 OP_OVER', script)

        script = [types.Five(), types.One(), types.Roll(), types.Drop()]
        self._do_test('OP_5 OP_NIP', script)

        script = [types.Zero(), types.Pick()]
        self._do_test('OP_DUP', script)

        script = [types.Five(), types.Zero(), types.Roll()]
        self._do_test('OP_5', script)

        script = [types.Five(), types.Six(), types.One(), types.Roll(), types.One(), types.Roll()]
        self._do_test('OP_5 OP_6', script)

        script = [types.Five(), types.Five(), types.Five(), types.Drop(), types.Drop()]
        self._do_test('OP_5 OP_5 OP_5 OP_2DROP', script)

    def test_arithmetic_shortcut_ops(self):
        for script in [
            [types.Five(), types.One(), types.Add()],
            [types.One(), types.Five(), types.Add()],
        ]:
            self._do_test('OP_5 OP_1ADD', script)

        self._do_test('OP_1ADD', [types.Assumption('testItem'), types.One(), types.Add()])

        script = [types.Five(), types.One(), types.Sub()]
        self._do_test('OP_5 OP_1SUB', script)

        for script in [
            [types.Five(), types.Two(), types.Mul()],
            [types.Two(), types.Five(), types.Mul()],
        ]:
            self._do_test('OP_5 OP_2MUL', script)

        self._do_test('OP_2MUL', [types.Assumption('testItem'), types.Two(), types.Mul()])

        script = [types.Five(), types.Two(), types.Div()]
        self._do_test('OP_5 OP_2DIV', script)

        script = [types.Five(), types.One(), types.Negate()]
        self._do_test('OP_5 OP_1NEGATE', script)

    def test_conditional_shortcut_ops(self):
        script = [types.Five(), types.Not(), types.If(), types.Two(), types.EndIf()]
        self._do_test('OP_5 OP_NOTIF OP_2 OP_ENDIF', script)

    def test_hash_shortcut_ops(self):
        script = [types.Five(), types.Sha256(), types.Sha256()]
        self._do_test('OP_5 OP_HASH256', script)

        script = [types.Five(), types.Sha256(), types.RipeMD160()]
        self._do_test('OP_5 OP_HASH160', script)

    def test_remove_null_arithmetic(self):
        for script in [
            [types.Five(), types.Zero(), types.Add()],
            [types.Zero(), types.Five(), types.Add()],
            [types.Five(), types.Zero(), types.Sub()],
        ]:
            self._do_test('OP_5', script)

    def test_remove_null_conditionals(self):
        script = [types.Five(), types.If(), types.Else(), types.EndIf()]
        self._do_test('OP_5 OP_DROP', script)

    def test_remove_trailing_verifications(self):
        script = [types.Five(), types.Verify(), types.Verify()]
        self._do_test('OP_5', script)

    def test_use_arithmetic_ops(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Not()]
        self._do_test('OP_5 OP_5 OP_NUMNOTEQUAL', script)

        script = [types.Five(), types.Push(b'\x01\x02\x03\x04'), types.Equal(), types.Not()]
        self._do_test('OP_5 01020304 OP_NUMNOTEQUAL', script)

        # A value longer than 4 bytes won't be optimized this way.
        script = [types.Five(), types.Push(b'\x01\x02\x03\x04\x05'), types.Equal(), types.Not()]
        self._do_test('OP_5 0102030405 OP_EQUAL OP_NOT', script)

    def test_use_small_int_ops(self):
        script = [types.Push(b'\x05')]
        self._do_test('OP_5', script)

    def test_promote_return(self):
        for script in [
            [types.Five(), types.Return()],
            [types.Return(), types.Five(), types.Return()],
        ]:
            self._do_test('OP_RETURN OP_5', script)

    def test_commutative_operations(self):
        script = [types.Two(), types.Five(), types.Swap(), types.Add()]
        self._do_test('OP_2 OP_5 OP_ADD', script)

    def test_multiple_optimization_occurrences(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Verify(), types.Five(), types.Five(), types.Equal(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY OP_5 OP_5 OP_EQUALVERIFY', script)

class InlineTest(BaseOptimizationTest):
    def setUp(self):
        super(InlineTest, self).setUp()
        self._reset_table(['testItem'])

    def _reset_table(self, stack_items=None):
        self.symbol_table.clear()
        if stack_items is not None:
            self.symbol_table.add_stack_assumptions(stack_items)

    def test_implicit_assume(self):
        script = [types.Assumption('testItem'), types.Five(), types.Add()]
        self._do_test('OP_5 OP_ADD', script)

    def test_assume_to_pick_or_roll(self):
        script = [types.Five(), types.Assumption('testItem'), types.Add()]
        self._do_test('OP_5 OP_ADD', script)

        self._reset_table(['testItem'])
        script = [types.Five(), types.Five(), types.Assumption('testItem'), types.Add()]
        self._do_test('OP_5 OP_5 OP_2 OP_ROLL OP_ADD', script)

        self._reset_table(['testItem'])
        script = [types.Five(), types.Five(), types.Assumption('testItem'), types.Add(), types.Assumption('testItem')]
        self._do_test('OP_5 OP_5 OP_2 OP_PICK OP_ADD OP_2 OP_ROLL', script)

