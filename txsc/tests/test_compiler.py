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
        return Namespace(output_file=None, source_lang='txscript',
                target_lang='asm', verbosity=0)

    def _compile(self, src):
        self.compiler.setup_options(self._options())
        self.compiler.compile(src)
        return self.compiler.output()

Test = namedtuple('Test', ('expected', 'src'))

class CompileTxScriptTest(BaseCompilerTest):
    def _test(self, test):
        result = self._compile(test.src)
        errmsg = "'%s' != '%s' (source: '%s')" % (test.expected, result, test.src)
        self.assertEqual(test.expected, result, errmsg)

    def test_single_instruction(self):
        for src in ['5', '0x5', '0x05']:
            self.assertEqual('5', self._compile(src))

    def test_multi_line(self):
        for test in [
            Test('2 3 ADD 4 5 ADD', '2 + 3; 4 + 5'),
            Test('2 3 ADD 4 5 ADD', ['2 + 3;', '4 + 5']),
            Test('2 3 ADD 4 5 ADD 1', ['2 + 3;', '4 + 5;', '1']),
        ]:
            self._test(test)

    def test_single_assumption(self):
        for test in [
            Test('5 ADD', ['assume a;', 'a + 5']),
            Test('NEGATE', ['assume a;', '-a']),
        ]:
            self._test(test)

    def test_standard_tx(self):
        # P2PKH output script.
        src = ['assume sig, pubkey;',
               'verify hash160(pubkey) == \'1111111111111111111111111111111111111111\';',
               'checkSig(sig, pubkey);']
        self._test(Test('DUP HASH160 0x14 0x1111111111111111111111111111111111111111 EQUALVERIFY CHECKSIG', src))
