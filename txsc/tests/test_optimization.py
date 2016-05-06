import unittest

from txsc.ir.instructions import LInstructions
from txsc.ir.linear_optimizer import LinearOptimizer
import txsc.ir.linear_nodes as types

class BaseOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.optimizer = LinearOptimizer()

    def _do_test(self, expected, script):
        original = str(script)
        self.optimizer.optimize(script)
        expected = str(expected.split(' '))
        self.assertEqual(expected, str(script), '%s != %s (original: %s)' % (expected, str(script), original))

class OptimizationTest(BaseOptimizationTest):
    def test_repeated_ops(self):
        script = LInstructions([types.Five(), types.Five(), types.Five(),
                types.Drop(), types.Drop()])
        self._do_test('OP_5 OP_5 OP_5 OP_2DROP', script)

    def test_optimize_stack_ops(self):
        script = LInstructions([types.Five(), types.One(), types.Pick()])
        self._do_test('OP_5 OP_OVER', script)

        script = LInstructions([types.Five(), types.One(), types.Roll(), types.Drop()])
        self._do_test('OP_5 OP_NIP', script)

        script = LInstructions([types.Zero(), types.Pick()])
        self._do_test('OP_DUP', script)

        script = LInstructions([types.Five(), types.Zero(), types.Roll()])
        self._do_test('OP_5', script)

        script = LInstructions([types.Five(), types.Six(), types.One(), types.Roll(), types.One(), types.Roll()])
        self._do_test('OP_5 OP_6', script)

    def test_shortcut_ops(self):
        for script in [
            LInstructions([types.Five(), types.One(), types.Add()]),
            LInstructions([types.One(), types.Five(), types.Add()]),
        ]:
            self._do_test('OP_5 OP_1ADD', script)

        script = LInstructions([types.Five(), types.One(), types.Sub()])
        self._do_test('OP_5 OP_1SUB', script)

        for script in [
            LInstructions([types.Five(), types.Two(), types.Mul()]),
            LInstructions([types.Two(), types.Five(), types.Mul()]),
        ]:
            self._do_test('OP_5 OP_2MUL', script)

        script = LInstructions([types.Five(), types.Two(), types.Div()])
        self._do_test('OP_5 OP_2DIV', script)

        script = LInstructions([types.Five(), types.One(), types.Negate()])
        self._do_test('OP_5 OP_1NEGATE', script)

    def test_null_ops(self):
        for script in [
            LInstructions([types.Five(), types.Zero(), types.Add()]),
            LInstructions([types.Zero(), types.Five(), types.Add()]),
            LInstructions([types.Five(), types.Zero(), types.Sub()]),
        ]:
            self._do_test('OP_5', script)


    def test_merge_op_and_verify(self):
        script = LInstructions([types.Five(), types.Five(), types.Equal(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY', script)

        script = LInstructions([types.Five(), types.Five(), types.NumEqual(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_NUMEQUALVERIFY', script)

    def test_optimize_dup_and_checksig(self):
        script = LInstructions([types.Five(), types.Dup(), types.Six(), types.CheckSig()])
        self._do_test('OP_5 OP_6 OP_CHECKSIG', script)

    def test_optimize_hashes(self):
        script = LInstructions([types.Five(), types.Sha256(), types.Sha256()])
        self._do_test('OP_5 OP_HASH256', script)

        script = LInstructions([types.Five(), types.Sha256(), types.RipeMD160()])
        self._do_test('OP_5 OP_HASH160', script)

    def test_multiple_optimization_occurrences(self):
        script = LInstructions([types.Five(), types.Five(), types.Equal(), types.Verify(),
                               types.Five(), types.Five(), types.Equal(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY OP_5 OP_5 OP_EQUALVERIFY', script)

    def test_promote_return(self):
        for script in [
            LInstructions([types.Five(), types.Return()]),
            LInstructions([types.Return(), types.Five(), types.Return()]),
        ]:
            self._do_test('OP_RETURN OP_5', script)

class InlineTest(BaseOptimizationTest):
    def test_implicit_assume(self):
        script = LInstructions([types.Assumption('testItem', 0), types.Five(), types.Add()])
        self._do_test('OP_5 OP_ADD', script)

    def test_assume_to_pick_or_roll(self):
        script = LInstructions([types.Five(), types.Assumption('testItem', 0), types.Add()])
        self._do_test('OP_5 OP_SWAP OP_ADD', script)

        script = LInstructions([types.Five(), types.Five(), types.Assumption('testItem', 0), types.Add()])
        self._do_test('OP_5 OP_5 OP_2 OP_ROLL OP_ADD', script)

        script = LInstructions([types.Five(), types.Five(), types.Assumption('testItem', 0), types.Add(), types.Assumption('testItem', 0)])
        self._do_test('OP_5 OP_5 OP_2 OP_PICK OP_ADD OP_2 OP_ROLL', script)
