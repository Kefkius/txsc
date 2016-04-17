import unittest

from txsc.script_compiler import ScriptCompiler

class BaseBtcScriptTest(unittest.TestCase):
    @classmethod
    def setupClass(cls):
        cls.compiler = ScriptCompiler()

    def _do_compile(self, src, input='btc'):
        return self.compiler.input_languages[input]().process_source(src)

    def _do_test(self, expected, script, input='btc', output='asm'):
        instructions = self._do_compile(script, input)
        lang = self.compiler.output_languages[output]
        result = lang().compile_instructions(instructions)
        self.assertEqual(expected, result)

class TestBtcScript(BaseBtcScriptTest):
    def test_input(self):
        self._do_test('5', '55')
        self._do_test('2 5 ADD', '525593')
        self._do_test('0x01 0x46', '0146')

    def test_input_with_0x_prefix(self):
        self._do_test('2 5 ADD', '0x525593')

class TestBtcOutput(BaseBtcScriptTest):
    def _do_test(self, expected, script):
        super(TestBtcOutput, self)._do_test(expected, script, input='asm', output='btc')

    def test_output(self):
        self._do_test('55', '5')
        self._do_test('0146', '0x01 0x46')

