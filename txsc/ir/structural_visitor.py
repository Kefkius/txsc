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
        """Transform symbol into instructions.

        Assume item at node.depth -> OP_DEPTH node.stack_size SUB node.depth OP_ADD OP_PICK.
        """
        self.add_instruction(self.get_opcode_class('OP_DEPTH'))

        self.visit(structural_nodes.Push(self.int_to_bytearray(node.stack_size)))
        self.add_instruction(self.get_opcode_class('OP_SUB'))

        self.visit(structural_nodes.Push(self.int_to_bytearray(node.depth)))
        self.add_instruction(self.get_opcode_class('OP_ADD'))

        self.add_instruction(self.get_opcode_class('OP_PICK'))
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

