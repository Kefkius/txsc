import ast
import copy

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

from txsc.ir import linear_nodes
from txsc.ir import structural_nodes
from txsc.ir import formats

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
    if isinstance(op, (structural_nodes.Push, structural_nodes.Symbol)):
        return str(op)
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
        if not isinstance(op, structural_nodes.BinOpCode):
            return False
        linear = linear_nodes.opcode_by_name(op.name)
        if not linear or not issubclass(linear, linear_nodes.OpCode):
            return
        return linear.arithmetic


    def __init__(self, script=structural_nodes.Script()):
        self.script = script

    def get_function_body(self, call, symbol_table):
        """Get the function for call.

        This allows mutable values to be used as globals in functions.
        """
        symbol = symbol_table.lookup(call.name)
        args = symbol.value.args
        body = copy.deepcopy(symbol.value.body)

        # Figure out how many times each mutable name was changed before the function call.
        global_values = {}
        def traverse_tree_before_call(n):
            if isinstance(n, list):
                return map(traverse_tree_before_call, n)
            for child in ast.iter_child_nodes(n):
                if child == call:
                    break

                if isinstance(child, structural_nodes.Assignment):
                    value = global_values.get(child.name, -1)
                    value += 1
                    global_values[child.name] = value
                else:
                    traverse_tree_before_call(child)
        traverse_tree_before_call(self.script)

        # Now set the idx of each mutable global symbol used within the function body.
        arg_names = [i.id for i in args]
        def visit_stmt(stmt):
            if isinstance(stmt, structural_nodes.Assignment):
                if stmt.name in arg_names:
                    signature = '%s(%s)' % (call.name, ', '.join(arg_names))
                    raise Exception('In function %s: Cannot assign value to immutable function argument' % signature)

            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, structural_nodes.Symbol):
                    if child.name in arg_names:
                        continue

                    child.idx = global_values[child.name]
        map(visit_stmt, body)

        return body

    def dump(self, *args):
        return self.script.dump(*args)
