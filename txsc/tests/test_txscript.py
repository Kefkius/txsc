import unittest
import ast

from ply import yacc

from txsc.txscript import ScriptParser, ScriptTransformer
from txsc.txscript.script_transformer import ParsingCheckError


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
        self._test_transform('5 + 2;', "[BinOpCode('OP_ADD', Int(5), Int(2))]")
        self._test_transform('5 - 2;', "[BinOpCode('OP_SUB', Int(5), Int(2))]")
        self._test_transform('5 * 2;', "[BinOpCode('OP_MUL', Int(5), Int(2))]")
        self._test_transform('5 / 2;', "[BinOpCode('OP_DIV', Int(5), Int(2))]")
        self._test_transform('5 % 2;', "[BinOpCode('OP_MOD', Int(5), Int(2))]")

    def test_functions(self):
        self._test_transform('min(1, 2);', "[BinOpCode('OP_MIN', Int(1), Int(2))]")
        self._test_transform('max(1, 2);', "[BinOpCode('OP_MAX', Int(1), Int(2))]")
        self._test_transform('verify max(1, 2) == 2;', "[VerifyOpCode('OP_VERIFY', BinOpCode('OP_EQUAL', BinOpCode('OP_MAX', Int(1), Int(2)), Int(2)))]")

    def test_boolops(self):
        self._test_transform('5 or 2;', "[BinOpCode('OP_BOOLOR', Int(5), Int(2))]")
        self._test_transform('5 or 2 or 8;', "[BinOpCode('OP_BOOLOR', Int(5), BinOpCode('OP_BOOLOR', Int(2), Int(8)))]")
        self._test_transform('5 and 2;', "[BinOpCode('OP_BOOLAND', Int(5), Int(2))]")

class CompoundStatementTest(BaseScriptTransformerTest):
    def test_arithmetic(self):
        self._test_transform('5 + 2; 1 + 3;', "[BinOpCode('OP_ADD', Int(5), Int(2)), BinOpCode('OP_ADD', Int(1), Int(3))]")

    def test_functions(self):
        self._test_transform('min(1, 2); 100;', "[BinOpCode('OP_MIN', Int(1), Int(2)), Int(100)]")
        self._test_transform('min(1, 2) == 1; 100;', "[BinOpCode('OP_EQUAL', BinOpCode('OP_MIN', Int(1), Int(2)), Int(1)), Int(100)]")

    def test_trailing_semicolon(self):
        """Trailing semicolon should not cause a syntax failure."""
        self._test_transform('1 + 2; 3 + 4;', "[BinOpCode('OP_ADD', Int(1), Int(2)), BinOpCode('OP_ADD', Int(3), Int(4))]")

    def test_comment(self):
        self._test_transform('1 + 2;\n#Comment line.\n3 + 4;', "[BinOpCode('OP_ADD', Int(1), Int(2)), BinOpCode('OP_ADD', Int(3), Int(4))]")

class TypeTest(BaseScriptTransformerTest):
    def test_literal_bytes(self):
        self._test_transform("'04';", "[Bytes(0x04)]")
        for s in ["'004'", "'0004'"]:
            self._test_transform(s + ';', "[Bytes(0x0004)]")

    def test_literal_str_bytes(self):
        self._test_transform("\"a\";", "[Bytes(0x61)]")

    def test_literal_int(self):
        self._test_transform("4;", "[Int(4)]")

    def test_literal_hex_int(self):
        for s in ["0x4", "0x04", "0x004", "0x0004"]:
            self._test_transform(s + ';', "[Int(4)]")

class CheckTest(BaseScriptTransformerTest):
    def _test_check(self, src, expected_error=None):
        t = self._parse(src)
        if expected_error:
            self.assertRaises(expected_error, self.transformer.visit, t)
        else:
            self.transformer.visit(t)

    def test_check_hash160(self):
        for src in [
            # Too short.
            "'10101010101010101010101010101010101010'",
            # Too long.
            "'101010101010101010101010101010101010101010'",
        ]:
            self._test_check('check_hash160(%s);' % src, ParsingCheckError)

        self._test_check("check_hash160('1010101010101010101010101010101010101010');")

    def test_check_pubkey(self):
        for src in [
            # Too short.
            "'0210101010101010101010101010101010101010101010101010101010101010'",
            "'04101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010'",
            # Too long.
            "'02101010101010101010101010101010101010101010101010101010101010101010'",
            "'041010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010'",
            # Invalid first byte.
            "'041010101010101010101010101010101010101010101010101010101010101010'",
            "'0210101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010'",
            "'0310101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010'",
        ]:
            self._test_check('check_pubkey(%s);' % src, ParsingCheckError)

        self._test_check("check_pubkey('021010101010101010101010101010101010101010101010101010101010101010');")
        self._test_check("check_pubkey('0410101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010');")

    def test_address_to_hash160(self):
        for src in [
            "1111111111111111111114oLvT2",
            "M7uAERuQW2AotfyLDyewFGcLUDtAYu9v5V",
        ]:
            self._test_check('address_to_hash160("%s");' % src)

        for src in [
            "1111111111111111111114oLvT",
            "M7uAERuQW2AotfyLDyewFGcLUDtAYu9v5VA",
        ]:
            self._test_check('address_to_hash160("%s");' % src, ParsingCheckError)
