import unittest
from argparse import Namespace

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

    def _test(self, expected, src):
        result = self._compile(src)
        errmsg = "'%s' != '%s' (source: '%s')" % (expected, result, src)
        self.assertEqual(expected, result, errmsg)
