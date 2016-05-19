import unittest
from collections import namedtuple


from txsc.tests import BaseCompilerTest


Test = namedtuple('Test', ('expected', 'src'))

class CompileTxScriptTest(BaseCompilerTest):
    def _test(self, test):
        return super(CompileTxScriptTest, self)._test(test.expected, test.src)

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
            Test('0x03 0x525393 SWAP 7 ADD', 'assume a; raw(2 + 3); a + 7;'),
            Test('0x06 0x525393555494 SWAP 7 ADD', 'assume a; raw(2 + 3, 5 - 4); a + 7;'),
        ]:
            self._test(test)

    def test_mutable_value(self):
        for test in [
            Test('2 5 ADD', 'mutable varA = 2; varA + 5; varA = 20;'),
        ]:
            self._test(test)

    def test_standard_tx(self):
        # P2PKH output script.
        src = ['assume sig, pubkey;',
               'verify hash160(pubkey) == \'1111111111111111111111111111111111111111\';',
               'checkSig(sig, pubkey);']
        self._test(Test('DUP HASH160 0x14 0x1111111111111111111111111111111111111111 EQUALVERIFY CHECKSIG', src))

class CompileTxScriptFunctionTest(BaseCompilerTest):
    def _test(self, test):
        return super(CompileTxScriptFunctionTest, self)._test(test.expected, test.src)

    def test_define_function(self):
        for test in [
            Test('5 1ADD', ['func addFive(x) {x + 5;}', 'addFive(1);'])
        ]:
            self._test(test)

    def test_function_scope(self):
        for test in [
            Test('5 1ADD', ['b = 5;', 'func addFive(x) {x + b;}', 'addFive(1);'])
        ]:
            self._test(test)

class CompileBtcScriptTest(BaseCompilerTest):
    @classmethod
    def _options(cls):
        namespace = super(CompileBtcScriptTest, cls)._options()
        namespace.source_lang = 'btc'
        return namespace

    def _test(self, test):
        return super(CompileBtcScriptTest, self)._test(test.expected, test.src)

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

    def _test(self, test):
        return super(CompileAsmTest, self)._test(test.expected, test.src)

    def test_asm(self):
        for test in [
            Test('2 5 ADD', '2 5 ADD'),
        ]:
            self._test(test)

