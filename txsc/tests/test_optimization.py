import unittest

from txsc.ir.instructions import Instructions
from txsc.optimize import Optimizer
import txsc.ir.linear_nodes as types

class BaseOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.optimizer = Optimizer()

    def _do_test(self, expected, script):
        self.optimizer.optimize(script)
        expected = str(expected.split(' '))
        self.assertEqual(expected, str(script))

class OptimizationTest(BaseOptimizationTest):
    def test_repeated_ops(self):
        script = Instructions([types.Five(), types.Five(), types.Five(),
                types.Drop(), types.Drop()])
        self._do_test('OP_5 OP_5 OP_5 OP_2DROP', script)

    def test_optimize_stack_ops(self):
        script = Instructions([types.Five(), types.One(), types.Pick()])
        self._do_test('OP_5 OP_OVER', script)

        script = Instructions([types.Five(), types.One(), types.Roll(), types.Drop()])
        self._do_test('OP_5 OP_NIP', script)

        script = Instructions([types.Zero(), types.Pick()])
        self._do_test('OP_DUP', script)

    def test_shortcut_ops(self):
        script = Instructions([types.Five(), types.One(), types.Add()])
        self._do_test('OP_5 OP_1ADD', script)

        script = Instructions([types.Five(), types.One(), types.Sub()])
        self._do_test('OP_5 OP_1SUB', script)

        script = Instructions([types.Five(), types.Two(), types.Mul()])
        self._do_test('OP_5 OP_2MUL', script)

        script = Instructions([types.Five(), types.Two(), types.Div()])
        self._do_test('OP_5 OP_2DIV', script)

        script = Instructions([types.Five(), types.One(), types.Negate()])
        self._do_test('OP_5 OP_1NEGATE', script)

    def test_merge_op_and_verify(self):
        script = Instructions([types.Five(), types.Five(), types.Equal(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY', script)

        script = Instructions([types.Five(), types.Five(), types.NumEqual(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_NUMEQUALVERIFY', script)

    def test_optimize_dup_and_checksig(self):
        script = Instructions([types.Five(), types.Dup(), types.Six(), types.CheckSig()])
        self._do_test('OP_5 OP_6 OP_CHECKSIG', script)

    def test_optimize_hashes(self):
        script = Instructions([types.Five(), types.Sha256(), types.Sha256()])
        self._do_test('OP_5 OP_HASH256', script)

        script = Instructions([types.Five(), types.Sha256(), types.RipeMD160()])
        self._do_test('OP_5 OP_HASH160', script)

    def test_multiple_optimization_occurrences(self):
        script = Instructions([types.Five(), types.Five(), types.Equal(), types.Verify(),
                               types.Five(), types.Five(), types.Equal(), types.Verify()])
        self._do_test('OP_5 OP_5 OP_EQUALVERIFY OP_5 OP_5 OP_EQUALVERIFY', script)
