import unittest
from argparse import Namespace
from collections import namedtuple


from txsc.script_compiler import ScriptCompiler


class BaseCompilerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = ScriptCompiler()

    @classmethod
    def _options(cls):
        return Namespace(optimization=1, output_file=None, source_lang='txscript',
                target_lang='asm', verbosity=0)

    def _compile(self, src):
        self.compiler.setup_options(self._options())
        self.compiler.compile(src)
        return self.compiler.output()

    def _test(self, test):
        result = self._compile(test.src)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result, test.src)
        self.assertEqual(test.expected, result, errmsg)

Test = namedtuple('Test', ('expected', 'src'))

class CompileTxScriptTest(BaseCompilerTest):

    def test_single_instruction(self):
        for src in ['5;', '0x5;', '0x05;']:
            self.assertEqual('5', self._compile(src))

    def test_multi_line(self):
        for test in [
            Test('2 3 ADD 4 5 ADD', '2 + 3; 4 + 5;'),
            Test('2 3 ADD 4 5 ADD', ['2 + 3;', '4 + 5;']),
            Test('2 3 ADD 4 5 ADD 1', ['2 + 3;', '4 + 5;', '1;']),
        ]:
            self._test(test)

    def test_single_assumption(self):
        for test in [
            Test('5 ADD', ['assume a;', 'a + 5;']),
            Test('NEGATE', ['assume a;', '-a;']),
        ]:
            self._test(test)

    def test_inner_script(self):
        for test in [
            Test('0x03 0x525393 SWAP 7 ADD', 'assume a; {2 + 3;} a + 7;'),
            Test('0x06 0x525393555494 SWAP 7 ADD', 'assume a; {2 + 3; 5 - 4;} a + 7;'),
        ]:
            self._test(test)

    def test_standard_tx(self):
        # P2PKH output script.
        src = ['assume sig, pubkey;',
               'verify hash160(pubkey) == \'1111111111111111111111111111111111111111\';',
               'checkSig(sig, pubkey);']
        self._test(Test('DUP HASH160 0x14 0x1111111111111111111111111111111111111111 EQUALVERIFY CHECKSIG', src))

class CompileBtcScriptTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(CompileBtcScriptTest, cls)._options()
        namespace.source_lang = 'btc'
        return namespace

    def test_btc(self):
        for test in [
            Test('2 5 ADD', '525593'),
        ]:
            self._test(test)

class CompileAsmTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(CompileAsmTest, cls)._options()
        namespace.source_lang = 'asm'
        return namespace

    def test_asm(self):
        for test in [
            Test('2 5 ADD', '2 5 ADD'),
        ]:
            self._test(test)


EqualTest = namedtuple('EqualTest', ('expected', 'src1', 'src2'))
class CompileTxScriptOptimizationsTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(CompileTxScriptOptimizationsTest, cls)._options()
        # Optimization is not set to 3 because we don't want the constant
        # expressions to be evaluated.
        namespace.optimization = 2
        return namespace

    def _test(self, test):
        result1 = self._compile(test.src1)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result1, test.src1)
        self.assertEqual(test.expected, result1, errmsg)

        result2 = self._compile(test.src2)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result2, test.src2)
        self.assertEqual(test.expected, result2, errmsg)

        self.assertEqual(result1, result2)

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
