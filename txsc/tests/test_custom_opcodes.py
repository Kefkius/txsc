import unittest

from txsc.btcscript import BtcScriptLanguage
from txsc.ir import linear_nodes as lir
from txsc.ir import structural_nodes as sir
from txsc.ir.instructions import SInstructions
from txsc.ir.structural_visitor import StructuralVisitor


class Foo(lir.OpCode):
    _numeric_value = 0xc0
    name = 'OP_FOO'
    delta = 0

class CustomOpCodeSet(lir.OpCodeSet):
    @classmethod
    def opcode_classes(cls):
        d = super(CustomOpCodeSet, cls).opcode_classes()
        d['OP_FOO'] = Foo
        return d

    @classmethod
    def opcode_values_by_name(cls):
        d = super(CustomOpCodeSet, cls).opcode_values_by_name()
        d['OP_FOO'] = Foo._numeric_value
        return d

def setUpModule():
    lir.set_opcode_set_cls(CustomOpCodeSet)

def tearDownModule():
    lir.set_opcode_set_cls(lir.OpCodeSet)


class CustomOpcodeTest(unittest.TestCase):
    def _linearize(self, structural):
        return StructuralVisitor().transform(SInstructions(structural))

    def _compile(self, linear):
        return BtcScriptLanguage().compile_instructions(linear)

    def test_op(self):
        op = sir.OpCode(name='OP_FOO')
        op.lineno = 0
        push = sir.Bytes('01')
        push.lineno = 0
        s = sir.Script(statements=[op, push])

        ops = self._linearize(s)
        self.assertEqual("['OP_FOO', 'OP_1']", str(ops))

        self.assertEqual('c051', self._compile(ops))
