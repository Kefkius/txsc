import ast
import copy
from functools import wraps
import logging

import hexs

from txsc.symbols import SymbolTable, SymbolType, ImmutableError, MultipleDeclarationsError, UndeclaredError
from txsc.transformer import BaseTransformer
from txsc.ir import formats
from txsc.ir.instructions import SInstructions, format_structural_op
from txsc.ir.structural_visitor import SIROptions, BaseStructuralVisitor, IRError, IRStrictNumError, IRTypeError
import txsc.ir.structural_nodes as types


def get_const(op):
    """Get whether op represents a constant value."""
    return isinstance(op, (types.Int, types.Push))

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

class StructuralOptimizer(BaseStructuralVisitor):
    """Performs optimizations on the structural IR."""
    def __init__(self, options=SIROptions()):
        super(StructuralOptimizer, self).__init__(options)
        self.evaluator = ConstEvaluator(self)

    def optimize(self, instructions, symbol_table):
        self.evaluator.enabled = self.options.evaluate_expressions
        self.evaluator.strict_num = self.options.strict_num
        self.script = instructions
        script = instructions.script
        self.symbol_table = SymbolTable.clone(symbol_table)

        new = []
        for stmt in script.statements:
            result = self.visit(stmt)
            if isinstance(result, list):
                new.extend(result)
            else:
                new.append(result)
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
            if symbol and symbol.type_ == SymbolType.StackItem:
                return True
            return False

        def has_assumption(n):
            """Return whether a BinOpCode contains an assumption."""
            if not isinstance(n, types.BinOpCode):
                return False
            return any(is_assumption(i) for i in [n.left, n.right])

        def should_commute(n):
            return is_assumption(n) or has_assumption(n)

        # Commute operands of different operations.
        # e.g. 2 + assumption + 3 --> 2 + 3 + assumption
        if self.is_commutative(node) and has_assumption(node.left) and node.left.name == node.name:
            # Move the assumption so we can be sure it's in the attribute 'right'.
            if is_assumption(node.left.left):
                node.left.left, node.left.right = node.left.right, node.left.left

            self.debug('Commuting operations for %s and %s' % (format_structural_op(node.left), format_structural_op(node.right)), node.lineno)
            right = node.right
            node.right = node.left.right
            node.left.right = right

        if should_commute(node.left) or not should_commute(node.right):
            return

        if self.is_commutative(node):
            self.debug('Commuting operands for %s' % format_structural_op(node), node.lineno)
            node.left, node.right = node.right, node.left
        elif self.has_logical_equivalent(node):
            logmsg = 'Replacing %s with logical equivalent ' % format_structural_op(node)
            node.name = logical_equivalents[node.name]
            node.left, node.right = node.right, node.left
            logmsg += format_structural_op(node)
            self.debug(logmsg, node.lineno)

    def visit(self, node):
        method = getattr(self, 'visit_%s' % node.__class__.__name__, None)
        if not method:
            return node
        try:
            return method(node)
        except IRError as e:
            raise e.__class__(e.args[0], node.lineno)

    def visit_Declaration(self, node):
        self.add_Declaration(node)
        return node

    def visit_Assignment(self, node):
        assignment = self.parse_Assignment(node)
        assignment.value = self.visit(assignment.value)
        self.add_Assignment(assignment)
        return node

    def visit_Symbol(self, node):
        """Attempt to simplify the value of a symbol."""
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('Symbol "%s" was not declared.' % node.name)
        value = symbol.value

        # Constant value.
        if get_const(value):
            return value
        # Try to evaluate and/or optimize the expression.
        if symbol.type_ == SymbolType.Expr:
            expr = self.visit(value)
            if get_const(expr):
                symbol.value = expr
                symbol.type_ = SInstructions.get_symbol_type_for_node(expr)
                return expr

        return node

    def visit_UnaryOpCode(self, node):
        self.check_types(node)
        node.operand = self.visit(node.operand)
        # Return the node if its operand isn't a constant value.
        if not get_const(node.operand):
            return node

        return self.evaluator.eval_op(node, node.name, node.operand) or node

    def visit_BinOpCode(self, node):
        self.check_types(node)
        # Optimize order if commutative.
        self.commute_operands(node)

        node.left, node.right = self.map_visit([node.left, node.right])

        # Return the node if both operands aren't constant values.
        if not get_all_const(node.left, node.right):
            return node

        result = self.evaluator.eval_op(node, node.name, node.left, node.right)
        if result:
            self.debug('Optimizing %s to %s' % (format_structural_op(node), format_structural_op(result)), result.lineno)
        return result or node

    def visit_VariableArgsOpCode(self, node):
        self.check_types(node)
        node.operands = self.map_visit(node.operands)
        # Return the node if not all operands are constant values.
        if not get_all_const(*node.operands):
            return node

        result = self.evaluator.eval_op(node, node.name, *node.operands)
        return result or node

    def visit_VerifyOpCode(self, node):
        node.test = self.visit(node.test)
        return node

    def visit_Return(self, node):
        node.value = self.visit(node.value)
        return node.value

    def visit_FunctionCall(self, node):
        node.args = self.map_visit(node.args)
        func = self.add_FunctionCall(node)
        body = copy.deepcopy(func.body)

        new_body = self.map_visit(body)
        self.symbol_table.end_scope()

        # If optimization succeeded, return the result.
        # Otherwise, return the original node.
        if new_body != body:
            return new_body[0] if len(new_body) == 1 else new_body
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
    def __init__(self, parent):
        self.parent = parent
        self.enabled = True
        self.strict_num = False
        self.node = None

    def strict_num(method):
        """Decorator that checks if numbers are valid."""
        @wraps(method)
        def wrapper(self, *args):
            args = map(int, args)
            valid = [formats.is_strict_num(i) for i in args]
            if False in valid:
                msg = 'Input value to %s is longer than 4 bytes: 0x%x' % (method.__name__, args[valid.index(False)])
                if self.strict_num:
                    self.parent.error(msg, self.node.lineno)
                    raise IRStrictNumError(msg)
                else:
                    self.parent.warning(msg, self.node.lineno)
            return method(self, *args)
        return wrapper

    def eval_op(self, node, op_name, *args):
        """Evaluate an opcode."""
        if not self.enabled:
            return

        method = getattr(self, op_name, None)
        if method is None:
            return
        self.node = node
        result = method(*args)
        # Convert result to a Push instance.
        if isinstance(result, int):
            result = types.Int.coerce(result)
        elif isinstance(result, str):
            result = types.Push.coerce(result)
        result.lineno = node.lineno

        if not formats.is_strict_num(int(result)):
            args_str = str(map(str, args))[1:-1] # Remove brackets
            msg = 'Result of %s is longer than 4 bytes: 0x%x' % (format_structural_op(node), result)
            if self.strict_num:
                self.parent.error(msg, node.lineno)
                raise IRStrictNumError(msg)
            else:
                self.parent.warning(msg, node.lineno)
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

    @strict_num
    def OP_INVERT(self, value):
        return ~value

    @strict_num
    def OP_AND(self, left, right):
        return left & right

    @strict_num
    def OP_OR(self, left, right):
        return left | right

    @strict_num
    def OP_XOR(self, left, right):
        return left ^ right

    @params(str)
    def OP_CAT(self, left, right):
        return left + right

    @params(str)
    def OP_SIZE(self, s):
        return len(s) / 2

    @params(str)
    def OP_EQUAL(self, left, right):
        return left == right
