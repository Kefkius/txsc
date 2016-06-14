import unittest
from collections import namedtuple

from txsc.ir.instructions import LInstructions, SInstructions
from txsc.symbols import SymbolType
from txsc.ir import linear_nodes as lir
from txsc.ir import structural_nodes as sir

TypeTest = namedtuple('TypeTest', ('node', 'expected_type'))
class TypeCheckingTest(unittest.TestCase):
    def _test(self, type_test):
        type_name = SInstructions.get_symbol_type_for_node(type_test.node)
        msg = '%s != %s (node: %s)' % (type_test.expected_type, type_name, type_test.node)
        self.assertEqual(type_test.expected_type, type_name, msg)

    def test_basic_types(self):
        for test in [
            TypeTest(sir.Int(5), SymbolType.Integer),
            TypeTest(sir.Bytes('05'), SymbolType.ByteArray),
            TypeTest(sir.Symbol('foo'), SymbolType.Symbol),
        ]:
            self._test(test)

    def test_arithmetic(self):
        """Test that arithmetic operations result in integers."""
        for test in [
            TypeTest(sir.BinOpCode(name = 'OP_ADD', left = sir.Int(5), right = sir.Int(6)), SymbolType.Integer),
            TypeTest(sir.BinOpCode(name = 'OP_ADD', left = sir.Bytes('05'), right = sir.Bytes('06')), SymbolType.Integer),
        ]:
            self._test(test)

    def test_operations(self):
        for test in [
            TypeTest(sir.UnaryOpCode(name = 'OP_SHA1', operand = sir.Int(5)), SymbolType.ByteArray),
            TypeTest(sir.UnaryOpCode(name = 'OP_SHA1', operand = sir.Symbol('foo')), SymbolType.Expr),
            TypeTest(sir.VariableArgsOpCode(name='OP_CHECKMULTISIG', operands=[sir.Int(1), sir.Bytes('111111'), sir.Bytes('222222'), sir.Int(2)]),
                    SymbolType.ByteArray),
        ]:
            self._test(test)

class StructuralFormatTest(unittest.TestCase):

    def test_unary_op(self):
        for name, expected in [
            ('OP_1ADD', '05++'),
            ('OP_1SUB', '05--'),
            ('OP_2MUL', '05 * 2'),
            ('OP_2DIV', '05 / 2'),
            ('OP_NEGATE', '-05'),
            ('OP_ABS', '|05|'),
        ]:
            op = sir.UnaryOpCode(name = name, operand = sir.Bytes('05'))
            self.assertEqual(expected, SInstructions.format_op(op))

    def test_binary_op(self):
        for name, expected in [
            ('OP_ADD', '05 + 06'),
            ('OP_SUB', '05 - 06'),
            ('OP_MUL', '05 * 06'),
            ('OP_DIV', '05 / 06'),
            ('OP_MOD', '05 % 06'),
            ('OP_LSHIFT', '05 << 06'),
            ('OP_RSHIFT', '05 >> 06'),

            ('OP_BOOLAND', '05 and 06'),
            ('OP_BOOLOR', '05 or 06'),

            ('OP_NUMEQUAL', '05 == 06'),
            ('OP_NUMNOTEQUAL', '05 != 06'),
            ('OP_LESSTHAN', '05 < 06'),
            ('OP_GREATERTHAN', '05 > 06'),
            ('OP_LESSTHANOREQUAL', '05 <= 06'),
            ('OP_GREATERTHANOREQUAL', '05 >= 06'),
        ]:
            op = sir.BinOpCode(name = name, left = sir.Bytes('05'), right = sir.Bytes('06'))
            self.assertEqual(expected, SInstructions.format_op(op))

    def test_script(self):
        for node, expected in [
            (sir.Script(statements=[sir.Int(5)]), '5;'),
            (sir.Script(statements=[sir.Int(5), sir.Int(6)]), '5; 6;'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))

    def test_innerscript(self):
        for node, expected in [
            (sir.InnerScript(statements=[sir.Int(5)]), '5;'),
            (sir.InnerScript(statements=[sir.Int(5), sir.Int(6)]), '5; 6;'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))

    def test_assignments(self):
        for node, expected in [
            (sir.Declaration(name='foo', value=sir.Int(5), type_=SymbolType.Integer, mutable=True), 'let mutable foo = 5'),
            (sir.Declaration(name='foo', value=sir.Int(5), type_=SymbolType.Integer, mutable=False), 'let foo = 5'),
            (sir.Assignment(name='foo', value=sir.Int(5), type_=SymbolType.Integer), 'foo = 5'),
            (sir.Assignment(name='foo', value=sir.Bytes('05'), type_=SymbolType.Integer), 'foo = 05'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))

    def test_function(self):
        for node, expected in [
            (sir.Function(name='foo', args=[sir.Symbol('a')],
                    body=[sir.BinOpCode(name='OP_ADD', left=sir.Symbol('a'), right=sir.Int(2))]), 'func foo(a) {a + 2;}'),
            (sir.Function(name='foo', args=[sir.Symbol('a')],
                    body=[sir.BinOpCode(name='OP_ADD', left=sir.Symbol('a'), right=sir.Int(2)), sir.Int(5)]), 'func foo(a) {a + 2; 5;}'),
            (sir.Function(name='foo', args=[sir.Symbol('a'), sir.Symbol('b')],
                    body=[sir.BinOpCode(name='OP_ADD', left=sir.Symbol('a'), right=sir.Symbol('b')), sir.Int(5)]), 'func foo(a, b) {a + b; 5;}'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))

    def test_function_call(self):
        for node, expected in [
            (sir.FunctionCall(name='foo', args=[]), 'foo()'),
            (sir.FunctionCall(name='foo', args=[sir.Int(5)]), 'foo(5)'),
            (sir.FunctionCall(name='foo', args=[sir.Int(5), sir.Int(6)]), 'foo(5, 6)'),
            (sir.FunctionCall(name='foo', args=[sir.Int(5), sir.Bytes('06')]), 'foo(5, 06)'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))

    def test_conditional(self):
        for node, expected in [
            (sir.If(test=sir.Int(1), truebranch=[sir.Int(5)], falsebranch=[]), 'if 1 {5;}'),
            (sir.If(test=sir.Int(1), truebranch=[sir.Int(5)], falsebranch=[sir.Int(6)]), 'if 1 {5;} else {6;}'),
            (sir.If(test=sir.Int(1), truebranch=[sir.Int(5)], falsebranch=[sir.Int(6), sir.Int(7)]), 'if 1 {5;} else {6; 7;}'),
        ]:
            self.assertEqual(expected, SInstructions.format_op(node))
