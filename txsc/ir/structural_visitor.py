from functools import wraps

from txsc.transformer import SourceVisitor
from txsc.ir import formats, structural_nodes
from txsc.ir.instructions import LInstructions
import txsc.ir.linear_nodes as types

def returnlist(func):
    """Decorator that ensures a function returns a list."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if not isinstance(result, list):
            if result is None:
                result = []
            else:
                result = [result]
        return result
    return wrapper

class StructuralVisitor(SourceVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None):
        self.symbol_table = symbol_table
        self.instructions = LInstructions(self.visit(node))
        return self.instructions

    @returnlist
    def visit_Script(self, node):
        return_value = []
        for stmt in node.statements:
            return_value.extend(self.visit(stmt))
        return return_value

    @returnlist
    def visit_InnerScript(self, node):
        ops = []
        for stmt in node.statements:
            ops.extend(self.visit(stmt))
        return types.InnerScript(ops=ops)

    @returnlist
    def visit_Assignment(self, node):
        return None

    @returnlist
    def visit_Symbol(self, node):
        if not self.symbol_table:
            raise Exception('Cannot process symbol: No symbol table was supplied.')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise Exception('Symbol "%s" was not declared.' % node.name)
        # Add an assumption for the stack item.
        if symbol.type_ == 'stack_item':
            return types.Assumption(symbol.name, symbol.value)
        # Push the bytes of the byte array.
        elif symbol.type_ in ['byte_array', 'integer']:
            return self.visit(structural_nodes.Push(''.join(symbol.value)))
        # If the type is an expression, then StructuralOptimizer could not simplify it.
        # Evaluate the expression as if it were encountered in the structural IR.
        elif symbol.type_ == 'expression':
            return self.visit(symbol.value)

    @returnlist
    def visit_Push(self, node):
        smallint = types.small_int_opcode(int(node))
        if smallint:
            return smallint()
        else:
            return types.Push(formats.hex_to_bytearray(node.data))

    @returnlist
    def visit_OpCode(self, node):
        op = types.opcode_by_name(node.name)()
        return op

    @returnlist
    def visit_VerifyOpCode(self, node):
        return_value = self.visit(node.test)
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_UnaryOpCode(self, node):
        return_value = self.visit(node.operand)
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_BinOpCode(self, node):
        return_value = self.visit(node.left)
        return_value.extend(self.visit(node.right))
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_VariableArgsOpCode(self, node):
        return_value = []
        for arg in node.operands:
            return_value.extend(self.visit(arg))
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

