import unittest

from txsc.ir import formats
from txsc.ir.instructions import LInstructions
from txsc.ir.linear_context import LinearContextualizer
import txsc.ir.linear_nodes as types

class BaseContextTest(unittest.TestCase):
    def setUp(self):
        self.contextualizer = LinearContextualizer()

    def _do_context(self, script):
        self.contextualizer.contextualize(script)

class PickRollTest(BaseContextTest):
    def test_small_int(self):
        script = LInstructions([types.Five(), types.Six(), types.Seven(), types.Two(), types.Pick()])
        self._do_context(script)
        pick = script[4]
        self.assertIsInstance(pick, types.Pick)
        self.assertEqual([1, 4], pick.args)
        node = script[pick.idx - pick.args[1]]
        self.assertEqual(5, node.value)

class TestIfDup(BaseContextTest):
    def test_small_int(self):
        items = [
            (LInstructions([types.One(), types.Two(), types.IfDup()]), 1),
            (LInstructions([types.One(), types.Zero(), types.IfDup()]), 0),
        ]
        for script, expected_delta in items:
            self._do_context(script)
            ifdup = script[2]
            self.assertIsInstance(ifdup, types.IfDup)
            self.assertEqual(expected_delta, ifdup.delta)

    def test_push(self):
        script = LInstructions([types.One(), types.Push(formats.int_to_bytearray(20)), types.IfDup()])
        self._do_context(script)
        ifdup = script[2]
        self.assertIsInstance(ifdup, types.IfDup)
        self.assertEqual(1, ifdup.delta)

class TestMultiSig(BaseContextTest):
    def test_multisig(self):
        sigs = [types.Push(formats.int_to_bytearray(i)) for i in [100]]
        pubs = [types.Push(formats.int_to_bytearray(i)) for i in [300, 400]]

        script = [types.Zero()] # Dummy value.
        script.extend(sigs + [types.One()]) # 1 signature.
        script.extend(pubs + [types.Two()]) # 2 public keys.
        script.append(types.CheckMultiSig())
        script = LInstructions(script)
        self._do_context(script)

        checkmultisig = script[6]
        self.assertIsInstance(checkmultisig, types.CheckMultiSig)
        self.assertEqual(2, checkmultisig.num_pubkeys)
        self.assertEqual(1, checkmultisig.num_sigs)
