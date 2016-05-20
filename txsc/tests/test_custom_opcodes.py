import unittest

from txsc.ir import linear_nodes as lir
from txsc.ir import structural_nodes as sir
from txsc.ir.instructions import SInstructions
from txsc.ir.structural_visitor import StructuralVisitor


class Foo(lir.OpCode):
    name = 'OP_FOO'
    delta = 0

def setUpModule():
    ops = lir.get_opcodes()
    ops[Foo.name] = Foo
    lir.set_opcodes(ops)

def tearDownModule():
    lir.reset_opcodes()


class CustomOpcodeTest(unittest.TestCase):
    def _linearize(self, structural):
        return StructuralVisitor().transform(SInstructions(structural))

    def test_op(self):
        op = sir.OpCode(name='OP_FOO')
        s = sir.Script(statements=[op, sir.Push('01')])

        ops = self._linearize(s)
        self.assertEqual("['OP_FOO', 'OP_1']", str(ops))
