from txsc.transformer import SourceVisitor
from txsc.ir import formats, structural_nodes
import txsc.ir.linear_nodes as types

class StructuralVisitor(SourceVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None):
        self.symbol_table = symbol_table
        self.visit(node)
        return self.instructions

    def visit_Assignment(self, node):
        return None

    def visit_Symbol(self, node):
        if not self.symbol_table:
            raise Exception('Cannot process symbol: No symbol table was supplied.')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise Exception('Symbol "%s" was not declared.' % node.name)
        # Add an assumption for the stack item.
        if symbol.type_ == 'stack_item':
            self.add_instruction(types.Assumption(symbol.name, symbol.value))
        # Push the bytes of the byte array.
        elif symbol.type_ == 'byte_array':
            self.visit(structural_nodes.Push(''.join(symbol.value)))
        # If the type is an expression, then StructuralOptimizer could not simplify it.
        # Evaluate the expression as if it were encountered in the structural IR.
        elif symbol.type_ == 'expression':
            self.visit(symbol.value)

    def visit_Push(self, node):
        try:
            smallint = self.get_small_int_class(int(node))
            self.add_instruction(smallint)
        except TypeError:
            self.add_instruction(types.Push(formats.hex_to_bytearray(node.data)))

    def visit_OpCode(self, node):
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)

    def visit_VerifyOpCode(self, node):
        self.visit(node.test)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)

    def visit_UnaryOpCode(self, node):
        self.visit(node.operand)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)

    def visit_BinOpCode(self, node):
        self.visit(node.left)
        self.visit(node.right)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)

    def visit_VariableArgsOpCode(self, node):
        for arg in node.operands:
            self.visit(arg)
        op = self.get_opcode_class(node.name)
        self.add_instruction(op)

