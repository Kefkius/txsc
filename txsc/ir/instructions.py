import ast
import copy

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

from txsc.ir import linear_nodes
from txsc.ir import structural_nodes
from txsc.ir import formats
from txsc.symbols import SymbolType

# Constants for instructions type.
LINEAR = 1
STRUCTURAL = 2
def get_instructions_class(instructions_type):
    """Get the class for instructions of type instructions_type."""
    if instructions_type == LINEAR:
        return LInstructions
    elif instructions_type == STRUCTURAL:
        return SInstructions


def format_structural_op(op):
    """Format an op for human-readability."""
    def format_statements(statements):
        return '; '.join(map(format_structural_op, statements)) + ';'
    def format_args(arguments):
        args = map(format_structural_op, arguments)
        args_str = ''
        for i, arg in enumerate(args):
            args_str += arg
            if i < len(args) - 1:
                args_str += ', '
        return args_str

    if isinstance(op, structural_nodes.Script):
        return format_statements(op.statements)
    elif isinstance(op, (structural_nodes.Int, structural_nodes.Push, structural_nodes.Symbol)):
        s = str(op)
        # Hex-encode numeric values.
        if isinstance(op, (structural_nodes.Int, structural_nodes.Push)) and abs(int(op)) > 16:
            s = hex(int(op))
        return s
    elif isinstance(op, structural_nodes.Declaration):
        return 'let %s%s = %s' % ('mutable ' if op.mutable else '', op.name, format_structural_op(op.value))
    elif isinstance(op, structural_nodes.Assignment):
        return '%s = %s' % (op.name, format_structural_op(op.value))
    elif isinstance(op, structural_nodes.Deletion):
        return 'del %s' % op.name
    elif isinstance(op, structural_nodes.Function):
        args_str = format_args(op.args)
        body_str = format_statements(op.body)
        return 'func %s(%s) {%s}' % (op.name, args_str, body_str)
    elif isinstance(op, structural_nodes.FunctionCall):
        args_str = format_args(op.args)
        return '%s(%s)' % (op.name, args_str)
    elif isinstance(op, structural_nodes.If):
        test = format_structural_op(op.test)
        true_branch = format_statements(op.truebranch)
        s = 'if %s {%s}' % (test, true_branch)
        if op.falsebranch:
            s += ' else {%s}' % format_statements(op.falsebranch)
        return s
    elif isinstance(op, structural_nodes.InnerScript):
        return format_statements(op.statements)
    if not hasattr(op, 'name'):
        return
    linear = linear_nodes.opcode_by_name(op.name)
    if not linear or not linear.opstr:
        return

    if linear.is_unary():
        return linear.opstr.format(format_structural_op(op.operand))
    elif linear.is_binary():
        return linear.opstr.format(*map(format_structural_op, [op.left, op.right]))
    elif linear.is_ternary():
        return linear.opstr.format(*map(format_structural_op, op.operands[0:3]))


class Instructions(object):
    """Base model for instructions."""
    pass

class LInstructions(Instructions, list):
    """Model for linear instructions."""
    ir_type = LINEAR
    @staticmethod
    def instruction_to_int(op):
        """Get the integer value that op (a nullary opcode) pushes."""
        if isinstance(op, linear_nodes.SmallIntOpCode):
            return op.value
        elif isinstance(op, linear_nodes.Push):
            return formats.bytearray_to_int(op.data)


    def __init__(self, *args):
        # Perform a deep copy if an LInstructions instance is passed.
        if len(args) == 1 and isinstance(args[0], LInstructions):
            return super(LInstructions, self).__init__(copy.deepcopy(args[0]))
        return super(LInstructions, self).__init__(*args)

    def __str__(self):
        return str(map(str, self))

    def copy_slice(self, start, end):
        """Create a copy of instructions from [start : end]."""
        return copy.deepcopy(self[start:end])

    def insert_slice(self, start, values):
        """Insert a list of instructions at start."""
        while values:
            self.insert(start, values.pop(-1))

    def replace_slice(self, start, end, values):
        """Replace instructions from [start : end] with values."""
        self[start:end] = values

    def matches_template(self, template, index, strict=True):
        """Returns whether a block that matches templates starts at index.

        If strict is True:
            - Push opcodes must push the same value that those in the template push.
            - Small int opcodes must have the same value that those in the template have.
            - Assumptions must have the same value that those in the template have.
        """
        for i in range(len(template)):
            if not template[i]:
                continue

            equal = template[i] == self[index + i]
            if strict and not equal:
                return False

            # Non-strict evaluation.
            template_item = template[i]
            script_item = self[index + i]
            if template_item.__class__.__name__ == 'SmallIntOpCode' and isinstance(script_item, linear_nodes.SmallIntOpCode):
                equal = True
            elif all(isinstance(item, linear_nodes.Push) for item in [script_item, template_item]):
                equal = True
            elif all(isinstance(item, linear_nodes.Assumption) for item in [script_item, template_item]):
                equal = True

            if not equal:
                return False

        return True

    def replace(self, start, length, callback):
        """Pass [start : length] instructions to callback and replace them with its result."""
        end = start + length
        values = self.copy_slice(start, end)
        self.replace_slice(start, end, callback(values))

    def replace_template(self, template, callback, strict=True):
        """Call callback with any instructions matching template."""
        idx = 0
        while 1:
            if idx >= len(self):
                break
            if (idx <= len(self) - len(template)) and self.matches_template(template, idx, strict):
                self.replace(idx, len(template), callback)
                idx += len(template)
            else:
                idx += 1

    def find_occurrences(self, op):
        """Return all the indices that op occurs at."""
        occurrences = []
        template = [op]
        for i in range(len(self)):
            if self.matches_template(template, i):
                occurrences.append(i)
        return occurrences

class SInstructions(Instructions):
    """Model for structural instructions."""
    ir_type = STRUCTURAL

    @staticmethod
    def format_op(op):
        """Format an op for human-readability."""
        return format_structural_op(op)

    @staticmethod
    def is_arithmetic_op(op):
        """Return whether op represents an arithmetic operation."""
        linear = linear_nodes.opcode_by_name(op.name)
        if not linear or not issubclass(linear, linear_nodes.OpCode):
            return False
        return linear.arithmetic

    @staticmethod
    def is_push_operation(op):
        """Return whether op pushes a value to the stack if used as a statement."""
        non_push_classes = (structural_nodes.Script, structural_nodes.If, structural_nodes.Function,
                structural_nodes.Declaration, structural_nodes.Assignment, structural_nodes.Deletion,
                structural_nodes.Return,)
        if isinstance(op, non_push_classes):
            return False
        return True

    @staticmethod
    def get_operation_type(op):
        """Perform type inference on op."""
        if not isinstance(op, structural_nodes.OpCode):
            raise TypeError('Argument must be an operation')
        # Arithmetic operations result in Integers.
        if SInstructions.is_arithmetic_op(op):
            return SymbolType.Integer
        args = op.get_args()
        # If any operand is a symbol, then the type is Expression.
        if any(isinstance(i, structural_nodes.Symbol) for i in args):
            return SymbolType.Expr
        return SymbolType.ByteArray

    @staticmethod
    def get_symbol_type_for_node(op):
        """Get the SymbolType that can represent op."""
        if isinstance(op, structural_nodes.Int):
            return SymbolType.Integer
        elif isinstance(op, structural_nodes.Push):
            return SymbolType.ByteArray
        elif isinstance(op, structural_nodes.Symbol):
            return SymbolType.Symbol
        elif isinstance(op, structural_nodes.Function):
            return SymbolType.Func
        elif isinstance(op, structural_nodes.OpCode):
            return SInstructions.get_operation_type(op)
        # If no other type qualifies, use expression.
        return SymbolType.Expr


    def __init__(self, script=structural_nodes.Script()):
        self.script = script

    def dump(self, *args):
        return self.script.dump(*args)
