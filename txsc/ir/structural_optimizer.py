import ast
from functools import wraps
import logging

import hexs

from txsc.transformer import BaseTransformer
from txsc.ir import formats
from txsc.ir.instructions import format_structural_op
import txsc.ir.structural_nodes as types

logger = logging.getLogger(__name__)

def get_const(op):
    """Get whether op represents a constant value."""
    return isinstance(op, types.Push)

def get_all_const(*ops):
    """Get whether ops all represent constant values."""
    return all(map(get_const, ops))

# Operations that are commutative.
# StructuralOptimizer will attempt to change the order
# of operands in these operations so that it requires less
# stack manipulation to execute them.
commutative_operations = (
    'OP_ADD', 'OP_MUL', 'OP_BOOLAND', 'OP_BOOLOR',
    'OP_NUMEQUAL', 'OP_NUMEQUALVERIFY', 'OP_NUMNOTEQUAL',
    'OP_MIN', 'OP_MAX',
    'OP_AND', 'OP_OR', 'OP_XOR', 'OP_EQUAL', 'OP_EQUALVERIFY',
)
# Logically equivalent operations.
# StructuralOptimizer will attempt to change the operators and
# the order of operands in these operations so that it requires less
# stack manipulation to execute them.
logical_equivalents = {
    'OP_LESSTHAN': 'OP_GREATERTHAN',
    'OP_GREATERTHAN': 'OP_LESSTHAN',
}

class StructuralOptimizer(BaseTransformer):
    """Performs optimizations on the structural IR."""
    def __init__(self):
        self.evaluator = ConstEvaluator()

    def optimize(self, instructions, symbol_table, evaluate_expressions=True, strict_num=False):
        self.evaluator.enabled = evaluate_expressions
        self.evaluator.strict_num = strict_num
        script = instructions.script
        self.symbol_table = symbol_table
        new = map(self.visit, script.statements)
        script.statements = filter(lambda i: i is not None, new)

    def is_commutative(self, node):
        """Get whether node represents a commutative operation."""
        return node.name in commutative_operations

    def has_logical_equivalent(self, node):
        """Get whether node represents an operation with a logical equivalent."""
        return node.name in logical_equivalents

    def commute_operands(self, node):
        """Attempt to reorder the operands of node."""
        def is_assumption(n):
            """Return whether a node is an assumption."""
            if not isinstance(n, types.Symbol):
                return False
            symbol = self.symbol_table.lookup(n.name)
            if symbol and symbol.type_ == 'stack_item':
                return True
            return False

        def has_assumption(n):
            """Return whether a BinOpCode contains an assumption."""
            if not isinstance(n, types.BinOpCode):
                return False
            return any(is_assumption(i) for i in [n.left, n.right])

        def should_commute(n):
            return is_assumption(n) or has_assumption(n)

        if should_commute(node.left) or not should_commute(node.right):
            return

        if self.is_commutative(node):
            logger.debug('Commuting operands for %s' % format_structural_op(node))
            node.left, node.right = node.right, node.left
        elif self.has_logical_equivalent(node):
            logmsg = 'Replacing %s with logical equivalent ' % format_structural_op(node)
            node.name = logical_equivalents[node.name]
            node.left, node.right = node.right, node.left
            logmsg += format_structural_op(node)
            logger.debug(logmsg)

    def visit(self, node):
        method = getattr(self, 'visit_%s' % node.__class__.__name__, None)
        if not method:
            return node
        return method(node)

    def visit_list(self, node):
        return types.Push(''.join(node))

    def visit_Assignment(self, node):
        node.value = self.visit(node.value)
        return node

    def visit_Symbol(self, node):
        """Attempt to simplify the value of a symbol."""
        symbol = self.symbol_table.lookup(node.name)
        value = symbol.value
        if symbol.mutable:
            value = value[node.idx]

        if symbol.type_ in ['byte_array', 'integer']:
            return types.Push(''.join(value))
        # Try to optimize the expression.
        if symbol.type_ == 'expression':
            expr = self.visit(value)
            if isinstance(expr, types.Push):
                if symbol.mutable:
                    symbol.value[node.idx] = formats.hex_to_list(expr.data)
                else:
                    symbol.value = formats.hex_to_list(expr.data)
                    symbol.type_ = self.symbol_table.ByteArray

                return expr

        return node

    def visit_UnaryOpCode(self, node):
        node.operand = self.visit(node.operand)
        # Return the node if its operand isn't a constant value.
        if not get_const(node.operand):
            return node

        return self.evaluator.eval_op(node.name, node.operand) or node

    def visit_BinOpCode(self, node):
        node.left, node.right = map(self.visit, [node.left, node.right])

        # Optimize order if commutative.
        self.commute_operands(node)
        # Return the node if both operands aren't constant values.
        if not get_all_const(node.left, node.right):
            return node

        result = self.evaluator.eval_op(node.name, node.left, node.right)
        if result:
            logger.debug('Optimizing %s to %s' % (format_structural_op(node), format_structural_op(result)))
        return result or node

    def visit_VariableArgsOpCode(self, node):
        node.operands = map(self.visit, node.operands)
        # Return the node if not all operands are constant values.
        if not get_all_const(*node.operands):
            return node

        result = self.evaluator.eval_op(node.name, *node.operands)
        return result or node

    def visit_VerifyOpCode(self, node):
        node.test = self.visit(node.test)
        return node

def params(cls):
    """Causes the arguments to a method to be converted to cls."""
    def method_decorator(method):
        @wraps(method)
        def wrapper(self, *args):
            return method(self, *map(cls, args))
        return wrapper
    return method_decorator

class ConstEvaluator(object):
    """Evaluates expressions containing only constant values."""
    def __init__(self):
        self.enabled = True
        self.strict_num = False

    def strict_num(method):
        """Decorator that checks if numbers are valid."""
        @wraps(method)
        def wrapper(self, *args):
            args = map(int, args)
            valid = [formats.is_strict_num(i) for i in args]
            if False in valid:
                msg = 'Input value is longer than 4 bytes: 0x%x' % args[valid.index(False)]
                if self.strict_num:
                    raise ValueError(msg)
                else:
                    logger.warning(msg)
            return method(self, *args)
        return wrapper

    def eval_op(self, op_name, *args):
        """Evaluate an opcode."""
        if not self.enabled:
            return

        method = getattr(self, op_name, None)
        if method is None:
            return
        result = method(*args)
        # Convert result to a Push instance.
        if isinstance(result, int):
            result = types.Push(hexs.hexs(result))
        elif isinstance(result, str):
            if len(result) % 2:
                result = '0' + result
            result = types.Push(hexs.format_hex(result))
        return result

    @strict_num
    def OP_ABS(self, value):
        return abs(value)

    @strict_num
    def OP_NOT(self, value):
        return int(value == 0)

    @strict_num
    def OP_0NOTEQUAL(self, value):
        return int(value != 0)

    @strict_num
    def OP_NEGATE(self, value):
        return -value

    @strict_num
    def OP_ADD(self, left, right):
        return left + right

    @strict_num
    def OP_SUB(self, left, right):
        return left - right

    @strict_num
    def OP_MUL(self, left, right):
        return left * right

    @strict_num
    def OP_DIV(self, left, right):
        return left / right

    @strict_num
    def OP_MOD(self, left, right):
        return left % right

    @strict_num
    def OP_LSHIFT(self, left, right):
        return left << right

    @strict_num
    def OP_RSHIFT(self, left, right):
        return left >> right

    @strict_num
    def OP_LESSTHAN(self, left, right):
        return left < right

    @strict_num
    def OP_LESSTHANOREQUAL(self, left, right):
        return left <= right

    @strict_num
    def OP_GREATERTHAN(self, left, right):
        return left > right

    @strict_num
    def OP_GREATERTHANOREQUAL(self, left, right):
        return left >= right

    @strict_num
    def OP_MIN(self, left, right):
        return min(left, right)

    @strict_num
    def OP_MAX(self, left, right):
        return max(left, right)

    @strict_num
    def OP_WITHIN(self, value, min_, max_):
        return min_ <= value and value < max_

    @strict_num
    def OP_NUMEQUAL(self, left, right):
        return left == right

    @strict_num
    def OP_NUMNOTEQUAL(self, left, right):
        return left != right

    @strict_num
    def OP_BOOLAND(self, left, right):
        return left != 0 and right != 0

    @strict_num
    def OP_BOOLOR(self, left, right):
        return left != 0 or right != 0


    @params(str)
    def OP_SIZE(self, s):
        return len(s) / 2

    @params(str)
    def OP_EQUAL(self, left, right):
        return left == right
