from txsc.transformer import SourceVisitor
from txsc.ir.instructions import Instructions
from txsc.ir import structural_nodes
import txsc.ir.linear_nodes as types

class StructuralVisitor(SourceVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node):
        self.visit(node)
        return self.instructions

    def visit_Assumption(self, node):
        assume = types.Assumption(node.name, node.depth)
        self.add_instruction(assume)
        return node

    def visit_Push(self, node):
        value = Instructions.decode_number(node.data)
        if value >= 0 and value <= 16:
            op = self.get_small_int_class(value)
            self.add_instruction(op)
        else:
            push = types.Push(data=node.data)
            self.add_instruction(push)
        return node

    def visit_OpCode(self, node):
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)
        return node

    def visit_VerifyOpCode(self, node):
        self.visit(node.test)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)
        return node

    def visit_UnaryOpCode(self, node):
        self.visit(node.operand)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)
        return node

    def visit_BinOpCode(self, node):
        self.visit(node.left)
        self.visit(node.right)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)
        return node

    def visit_VariableArgsOpCode(self, node):
        for arg in node.operands:
            self.visit(arg)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)
        return node

