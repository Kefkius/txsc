import unittest
import ast

from ply import yacc

from txsc.txscript import ScriptParser, ScriptTransformer


def setUpModule():
    parser = ScriptParser(debug=False)

class BaseScriptTransformerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transformer = ScriptTransformer()

    def _parse(self, s):
        t = yacc.parse(s)
        if not isinstance(t, ast.Module):
            t = ast.Module(body=t)
        ast.fix_missing_locations(t)
        return t

    def _test_transform(self, s, expected, top_node='Script'):
        """In calls to this method, we omit "Script()" for clarity."""
        expected = '%s(%s)' % (top_node, expected)
        t = self._parse(s)
        t = self.transformer.visit(t)
        self.assertEqual(expected, self.transformer.dump(t))

class SingleStatementTest(BaseScriptTransformerTest):
    def test_arithmetic(self):
        self._test_transform('5 + 2', "[BinOpCode('OP_ADD', Push(0x55), Push(0x52))]")
        self._test_transform('5 - 2', "[BinOpCode('OP_SUB', Push(0x55), Push(0x52))]")
        self._test_transform('5 * 2', "[BinOpCode('OP_MUL', Push(0x55), Push(0x52))]")
        self._test_transform('5 / 2', "[BinOpCode('OP_DIV', Push(0x55), Push(0x52))]")
        self._test_transform('5 % 2', "[BinOpCode('OP_MOD', Push(0x55), Push(0x52))]")

    def test_functions(self):
        self._test_transform('min(1, 2)', "[BinOpCode('OP_MIN', Push(0x51), Push(0x52))]")
        self._test_transform('max(1, 2)', "[BinOpCode('OP_MAX', Push(0x51), Push(0x52))]")
        self._test_transform('verify max(1, 2) == 2', "[VerifyOpCode('OP_VERIFY', BinOpCode('OP_EQUAL', BinOpCode('OP_MAX', Push(0x51), Push(0x52)), Push(0x52)))]")

class CompoundStatementTest(BaseScriptTransformerTest):
    def test_arithmetic(self):
        self._test_transform('5 + 2; 1 + 3', "[BinOpCode('OP_ADD', Push(0x55), Push(0x52)), BinOpCode('OP_ADD', Push(0x51), Push(0x53))]")

    def test_functions(self):
        self._test_transform('min(1, 2); 100', "[BinOpCode('OP_MIN', Push(0x51), Push(0x52)), Push(0x64)]")
        self._test_transform('min(1, 2) == 1; 100', "[BinOpCode('OP_EQUAL', BinOpCode('OP_MIN', Push(0x51), Push(0x52)), Push(0x51)), Push(0x64)]")

    def test_trailing_semicolon(self):
        """Trailing semicolon should not cause a syntax failure."""
        self._test_transform('1 + 2; 3 + 4;', "[BinOpCode('OP_ADD', Push(0x51), Push(0x52)), BinOpCode('OP_ADD', Push(0x53), Push(0x54))]")

    def test_comment(self):
        self._test_transform('1 + 2;\n#Comment line.\n3 + 4', "[BinOpCode('OP_ADD', Push(0x51), Push(0x52)), BinOpCode('OP_ADD', Push(0x53), Push(0x54))]")
