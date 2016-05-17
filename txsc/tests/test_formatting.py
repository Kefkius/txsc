import unittest
from collections import namedtuple

from txsc.ir.instructions import LInstructions, SInstructions
from txsc.ir import linear_nodes as lir
from txsc.ir import structural_nodes as sir


Test = namedtuple('UnaryTest', ('name', 'expected'))
class StructuralFormatTest(unittest.TestCase):

    def test_unary_op(self):
        for test in [
            Test('OP_1ADD', '05++'),
            Test('OP_1SUB', '05--'),
            Test('OP_2MUL', '05 * 2'),
            Test('OP_2DIV', '05 / 2'),
            Test('OP_NEGATE', '-05'),
            Test('OP_ABS', '|05|'),
        ]:
            op = sir.UnaryOpCode(name = test.name, operand = sir.Push('05'))
            self.assertEqual(test.expected, SInstructions.format_op(op))

    def test_binary_op(self):
        for test in [
            Test('OP_ADD', '05 + 06'),
            Test('OP_SUB', '05 - 06'),
            Test('OP_MUL', '05 * 06'),
            Test('OP_DIV', '05 / 06'),
            Test('OP_MOD', '05 % 06'),
            Test('OP_LSHIFT', '05 << 06'),
            Test('OP_RSHIFT', '05 >> 06'),

            Test('OP_BOOLAND', '05 and 06'),
            Test('OP_BOOLOR', '05 or 06'),

            Test('OP_NUMEQUAL', '05 == 06'),
            Test('OP_NUMNOTEQUAL', '05 != 06'),
            Test('OP_LESSTHAN', '05 < 06'),
            Test('OP_GREATERTHAN', '05 > 06'),
            Test('OP_LESSTHANOREQUAL', '05 <= 06'),
            Test('OP_GREATERTHANOREQUAL', '05 >= 06'),
        ]:
            op = sir.BinOpCode(name = test.name, left = sir.Push('05'), right = sir.Push('06'))
            self.assertEqual(test.expected, SInstructions.format_op(op))
