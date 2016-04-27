import ast
from functools import wraps

from txsc.transformer import BaseTransformer
from txsc.ir import formats
import txsc.ir.structural_nodes as types


class StructuralOptimizer(BaseTransformer):
    """Performs optimizations on the structural IR."""
    @staticmethod
    def instruction_to_int(op):
        """Get the integer value that op (a nullary opcode) pushes."""
        if isinstance(op, types.Push):
            return int(op)

    def __init__(self):
        self.evaluator = ConstEvaluator()

    def optimize(self, instructions, symbol_table):
        script = instructions.script
        self.symbol_table = symbol_table
        new = map(self.visit, script.statements)
        script.statements = filter(lambda i: i is not None, new)

    def visit(self, node):
        method = getattr(self, 'visit_%s' % node.__class__.__name__, None)
        if not method:
            return node
        return method(node)

    def visit_Assignment(self, node):
        node.value = self.visit(node.value)
        return node

    def visit_Symbol(self, node):
        """Attempt to simplify the value of a symbol."""
        symbol = self.symbol_table.lookup(node.name)
        # Try to optimize the expression.
        if symbol.type_ == 'expression':
            expr = self.visit(symbol.value)
            if isinstance(expr, types.Push):
                symbol.value = formats.hex_to_list(expr.data)
                symbol.type_ = self.symbol_table.ByteArray

        return node

    def visit_BinOpCode(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)

        # Return None if both can't be interpreted as integers.
        left, right = map(self.instruction_to_int, [node.left, node.right])
        if any(i is None for i in [left, right]):
            return node

        result = self.evaluator.eval_op(node.name, left, right)
        if result is not None:
            return types.Push(formats.strip_hex(hex(result)))
        return node


class ConstEvaluator(object):
    """Evaluates expressions containing only constant values."""
    def eval_op(self, op_name, *args):
        """Evaluate an opcode."""
        method = getattr(self, op_name, None)
        if method is None:
            return
        return method(*args)

    def OP_ADD(self, left, right):
        return left + right

    def OP_SUB(self, left, right):
        return left - right

    def OP_MUL(self, left, right):
        return left * right

    def OP_DIV(self, left, right):
        return left / right
