from txsc.transformer import SourceVisitor
from txsc.ir.instructions import Instructions
from txsc.ir import structural_nodes
import txsc.ir.linear_nodes as types

class StructuralVisitor(SourceVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None):
        self.symbol_table = symbol_table
        self.visit(node)
        return self.instructions

    def visit_Symbol(self, node):
        if not self.symbol_table:
            raise Exception('Cannot process symbol: No symbol table was supplied.')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise Exception('Symbol "%s" was not declared.' % node.name)
        if symbol.type_ == 'stack_item':
            self.add_instruction(types.Assumption(symbol.name, symbol.value))
        elif symbol.type_ == 'int':
            self.visit(structural_nodes.Push(self.int_to_bytearray(symbol.value)))
        elif symbol.type_ == 'byte_array':
            s = ''.join(symbol.value)
            self.visit(structural_nodes.Push(self.hex_to_bytearray(s)))

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

