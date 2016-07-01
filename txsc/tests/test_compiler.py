import unittest
from collections import namedtuple

from txsc.ir import IRError
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

    def test_duplicated_assumptions(self):
        for test in [
            Test('5 2 ROLL DUP ADD', ['assume a, b;', '5;', 'a + a;']),
            Test('5 SWAP DUP ADD', ['assume a, b;', '5;', 'b + b;']),
        ]:
            self._test(test)

    def test_augmented_assignment(self):
        for test in [
            Test('2 5 ADD', ['let mutable a = 2;', 'a += 5;', 'a;']),
            Test('2 5 ADD 3 SUB', ['let mutable a = 2;', 'a += 5;', 'a -= 3;', 'a;']),
            Test('2 5 ADD 3 SUB 6 LSHIFT', ['let mutable a = 2;', 'a += 5;', 'a -= 3;', 'a <<= 6;', 'a;']),
            # Unary augmented assignment.
            Test('2 5 ADD 1SUB', ['let mutable a = 2;', 'a += 5;', 'a--;', 'a;']),
        ]:
            self._test(test)

    def test_inner_script(self):
        for test in [
            Test('0x03 0x525393 SWAP 7 ADD', 'assume a; raw(2 + 3); a + 7;'),
            Test('0x06 0x525393555494 SWAP 7 ADD', 'assume a; raw(2 + 3, 5 - 4); a + 7;'),
            Test('0x04 0x03070809', "raw('070809');"),
        ]:
            self._test(test)

    def test_mutable_value(self):
        for test in [
            Test('2 5 ADD', 'let mutable varA = 2; varA + 5; varA = 20;'),
        ]:
            self._test(test)

    def test_standard_tx(self):
        # P2PKH output script.
        src = ['assume sig, pubkey;',
               'verify hash160(pubkey) == \'1111111111111111111111111111111111111111\';',
               'checkSig(sig, pubkey);']
        self._test(Test('DUP HASH160 0x14 0x1111111111111111111111111111111111111111 EQUALVERIFY CHECKSIG', src))

    def test_stack_state_scope(self):
        for test in [
            Test('SWAP DUP ADD', ['assume a, b;', 'a + a;']),
            Test('OVER DUP ADD 2 ROLL 2 ROLL ADD', ['assume a, b;', 'a + a;', 'a + b;']),
        ]:
            self._test(test)

class CompileTxScriptFunctionTest(BaseCompilerTest):
    def _test(self, test):
        return super(CompileTxScriptFunctionTest, self)._test(test.expected, test.src)

    def test_define_function(self):
        for test in [
            Test('5 1ADD', ['func int addFive(x) {return x + 5;}', 'addFive(1);'])
        ]:
            self._test(test)

    def test_function_scope(self):
        for test in [
            Test('5 1ADD', ['let b = 5;', 'func int addFive(x) {return x + b;}', 'addFive(1);']),
            Test('5 1ADD', ['let mutable b = 5;', 'func int addFive(x) {return x + b;}', 'addFive(1); b = 6;']),
            Test('5 1ADD 10 6 ADD', ['let mutable b = 5;', 'func int addFive(x) {return x + b;}', 'addFive(1); b = 6; addFive(10);']),
        ]:
            self._test(test)

class CompileTxScriptConditionalTest(BaseCompilerTest):
    def _test(self, test):
        return super(CompileTxScriptConditionalTest, self)._test(test.expected, test.src)

    def test_conditional(self):
        for test in [
            Test('5 IF 6 ELSE 7 ENDIF', ['let a = 5;' 'if a {6;} else {7;}']),
            Test('NOTIF 5 ENDIF', ['assume a;', 'if not a {5;}']),
            Test('SWAP IF SWAP ENDIF', ['assume a, b, c;' 'if b {a;} else {c;}']),
        ]:
            self._test(test)

    def test_empty_conditional(self):
        for test in [
            Test('IF 5 ENDIF', ['assume a;', 'if a {5;} else {}'],),
            Test('IF ELSE 5 ENDIF', ['assume a;', 'if a {} else {5;}'],),
            Test('DROP', ['assume a;', 'if a {} else {}'],),
        ]:
            self._test(test)

    def test_nested_conditional(self):
        for test in [
            Test('2 ROLL IF IF 5 ENDIF ENDIF', ['assume a, b, c;', 'if a { if c {5;} }'],),
            Test('2 ROLL IF IF 5 ELSE 6 ENDIF ENDIF', ['assume a, b, c;', 'if a { if c {5;} else {6;} }'],),
        ]:
            self._test(test)

    def test_error(self):
        """An exception should be thrown if an assumption is used after an uneven conditional.

        An uneven conditional means that a different number of stack items are present
        depending on whether the conditional test passes.
        """
        for src in [
            ['assume a;', 'if a == 5 {6;}', 'a;'],
            ['assume a, b, c;', 'if a { if c {5;} b; }'],
        ]:
            self.assertRaises(IRError, self._compile, src)

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

    def test_conditional_errors(self):
        # These scripts end without ending all conditionals.
        for src in [
            'IF 5 ELSE 6',
            'IF IF 5 ELSE 6 ENDIF',
        ]:
            self.assertRaises(IRError, self._compile, src)

        # This script has too many ENDIFs.
        self.assertRaises(IRError, self._compile, 'IF 5 ENDIF ENDIF')

        # This script has an ENDIF without any preceding conditional.
        self.assertRaises(IRError, self._compile, '5 ENDIF')

        # This script has an ELSE without any preceding conditional.
        self.assertRaises(IRError, self._compile, 'ELSE 5 ENDIF')
