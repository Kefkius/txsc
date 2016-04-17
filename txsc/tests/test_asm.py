import unittest

from txsc.asm import ASMLanguage

class BaseASMTest(unittest.TestCase):
    def _do_test(self, expected, script):
        expected = str(expected.split(' '))
        if not isinstance(script, list):
            script = [script]
        instructions = ASMLanguage().process_source(script)
        self.assertEqual(expected, str(instructions))

class TestInput(BaseASMTest):
    def test_input(self):
        self._do_test('OP_1 OP_2 OP_ADD', '1 2 ADD')
        self._do_test('70 OP_2 OP_ADD', '0x01 0x70 2 ADD')
