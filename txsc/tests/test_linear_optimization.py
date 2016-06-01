import unittest

from txsc.symbols import SymbolTable
from txsc.ir.instructions import LInstructions
from txsc.ir.linear_optimizer import LinearOptimizer
import txsc.ir.linear_nodes as types

class BaseOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.optimizer = LinearOptimizer()

    def _do_test(self, expected, ops_list):
        script = LInstructions(ops_list)
        original = str(script)
        self.optimizer.optimize(script, SymbolTable())
        expected = str(expected.split(' '))
        self.assertEqual(expected, str(script), '%s != %s (original: %s)' % (expected, str(script), original))

class OptimizationTest(BaseOptimizationTest):
    def test_repeated_ops(self):
        script = [types.Five(), types.Five(), types.Five(), types.Drop(), types.Drop()]
        self._do_test('OP_5 OP_5 OP_5 OP_2DROP', script)

    def test_optimize_stack_ops(self):
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

    def test_shortcut_ops(self):
        for script in [
            [types.Five(), types.One(), types.Add()],
            [types.One(), types.Five(), types.Add()],
        ]:
            self._do_test('OP_5 OP_1ADD', script)

        self._do_test('OP_1ADD', [types.Assumption('testItem', 0), types.One(), types.Add()])

        script = [types.Five(), types.One(), types.Sub()]
        self._do_test('OP_5 OP_1SUB', script)

        for script in [
            [types.Five(), types.Two(), types.Mul()],
            [types.Two(), types.Five(), types.Mul()],
        ]:
            self._do_test('OP_5 OP_2MUL', script)

        self._do_test('OP_2MUL', [types.Assumption('testItem', 0), types.Two(), types.Mul()])

        script = [types.Five(), types.Two(), types.Div()]
        self._do_test('OP_5 OP_2DIV', script)

        script = [types.Five(), types.One(), types.Negate()]
        self._do_test('OP_5 OP_1NEGATE', script)

    def test_null_ops(self):
        for script in [
            [types.Five(), types.Zero(), types.Add()],
            [types.Zero(), types.Five(), types.Add()],
            [types.Five(), types.Zero(), types.Sub()],
        ]:
            self._do_test('OP_5', script)


    def test_merge_op_and_verify(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY', script)

        script = [types.Five(), types.Five(), types.NumEqual(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_NUMEQUALVERIFY', script)

    def test_optimize_dup_and_checksig(self):
        script = [types.Five(), types.Dup(), types.Six(), types.CheckSig()]
        self._do_test('OP_5 OP_6 OP_CHECKSIG', script)

    def test_optimize_hashes(self):
        script = [types.Five(), types.Sha256(), types.Sha256()]
        self._do_test('OP_5 OP_HASH256', script)

        script = [types.Five(), types.Sha256(), types.RipeMD160()]
        self._do_test('OP_5 OP_HASH160', script)

    def test_arithmetic_ops(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Not()]
        self._do_test('OP_5 OP_5 OP_NUMNOTEQUAL', script)

        script = [types.Five(), types.Push(b'\x01\x02\x03\x04'), types.Equal(), types.Not()]
        self._do_test('OP_5 01020304 OP_NUMNOTEQUAL', script)

        # A value longer than 4 bytes won't be optimized this way.
        script = [types.Five(), types.Push(b'\x01\x02\x03\x04\x05'), types.Equal(), types.Not()]
        self._do_test('OP_5 0102030405 OP_EQUAL OP_NOT', script)

    def test_multiple_optimization_occurrences(self):
        script = [types.Five(), types.Five(), types.Equal(), types.Verify(), types.Five(), types.Five(), types.Equal(), types.Verify()]
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY OP_5 OP_5 OP_EQUALVERIFY', script)

    def test_promote_return(self):
        for script in [
            [types.Five(), types.Return()],
            [types.Return(), types.Five(), types.Return()],
        ]:
            self._do_test('OP_RETURN OP_5', script)

    def test_convert_to_small_int(self):
        script = [types.Push(b'\x05')]
        self._do_test('OP_5', script)

class InlineTest(BaseOptimizationTest):
    def test_implicit_assume(self):
        script = [types.Assumption('testItem', 0), types.Five(), types.Add()]
        self._do_test('OP_5 OP_ADD', script)

    def test_assume_to_pick_or_roll(self):
        script = [types.Five(), types.Assumption('testItem', 0), types.Add()]
        self._do_test('OP_5 OP_ADD', script)

        script = [types.Five(), types.Five(), types.Assumption('testItem', 0), types.Add()]
        self._do_test('OP_5 OP_5 OP_2 OP_ROLL OP_ADD', script)

        script = [types.Five(), types.Five(), types.Assumption('testItem', 0), types.Add(), types.Assumption('testItem', 0)]
        self._do_test('OP_5 OP_5 OP_2 OP_PICK OP_ADD OP_2 OP_ROLL', script)

class UnusedAssumptionsTest(BaseOptimizationTest):
    def setUp(self):
        super(UnusedAssumptionsTest, self).setUp()
        self.symbol_table = SymbolTable()

    def _do_test(self, expected, ops_list):
        script = LInstructions(ops_list)
        original = str(script)
        self.optimizer.optimize(script, self.symbol_table)
        expected = str(expected.split(' '))
        self.assertEqual(expected, str(script), '%s != %s (original: %s)' % (expected, str(script), original))

    def test_unused_top_assumption(self):
        self.symbol_table.add_stack_assumptions(['a', 'b', 'c'])
        script = [types.Assumption('a', 2), types.Assumption('b', 1), types.Add()]
        self._do_test('OP_DROP OP_ADD', script)

    def test_unused_assumptions(self):
        self.symbol_table.add_stack_assumptions(['a', 'b', 'c', 'd'])
        script = [types.Assumption('a', 3), types.Assumption('c', 1), types.Add()]
        self._do_test('OP_2 OP_ROLL OP_2DROP OP_ADD', script)

    def test_consecutive_top_item_drops(self):
        self.symbol_table.add_stack_assumptions(['a', 'b', 'c', 'd'])

        script = [types.Assumption('a', 3)]
        self._do_test('OP_2DROP OP_DROP', script)

        script = [types.Assumption('b', 2)]
        self._do_test('OP_2DROP OP_NIP', script)

        script = [types.Assumption('c', 1)]
        self._do_test('OP_3 OP_ROLL OP_DROP OP_2 OP_ROLL OP_2DROP', script)

        script = [types.Assumption('d', 0)]
        self._do_test('OP_3 OP_ROLL OP_DROP OP_2 OP_ROLL OP_DROP OP_NIP', script)
