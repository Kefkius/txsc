import copy

from txsc.ir import formats
from txsc.transformer import BaseTransformer
import txsc.ir.linear_nodes as types

class LIROptions(object):
    """Options for the linear intermediate representation.

    Attributes:
        allow_invalid_comparisons (bool): Whether to allow any data push to be compared
            with the result of an OP_HASH* opcode.
        inline_assumptions (bool): Whether to inline assumptions as stack operations.
        peephole_optimizations (bool): Whether to perform peephole optimizations.

    """
    def __init__(self, allow_invalid_comparisons=False,
                 inline_assumptions=True,
                 peephole_optimizations=True):
        self.allow_invalid_comparisons = allow_invalid_comparisons
        self.inline_assumptions = inline_assumptions
        self.peephole_optimizations = peephole_optimizations

class BaseLinearVisitor(BaseTransformer):
    """Base class for linear visitors."""
    @classmethod
    def op_for_int(self, value):
        """Get a small int or push operation for value."""
        cls = types.opcode_by_name('OP_%d'%value)
        if cls:
            return cls()
        value = formats.int_to_bytearray(value)
        return types.Push(data=value)

    def __init__(self, symbol_table, options=LIROptions()):
        super(BaseLinearVisitor, self).__init__()
        self.symbol_table = symbol_table
        self.options = options


class StackItem(object):
    """Model of an item on a stack."""
    def __init__(self, op):
        self.op = op

    def __str__(self):
        return str(self.op)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __int__(self):
        if isinstance(self.op, types.SmallIntOpCode):
            return self.op.value
        elif isinstance(self.op, types.Push):
            return formats.bytearray_to_int(self.op.data)
        raise TypeError('Cannot cast as int: %s' % (str(self)))

    def is_assumption(self):
        return type(self.op) is types.Assumption

class StateScope(object):
    def __init__(self, assumptions_offset=0, state=None):
        self.assumptions_offset = assumptions_offset
        self.state = state if state is not None else []

    @classmethod
    def copy(cls, other):
        return cls(assumptions_offset=other.assumptions_offset,
                   state=copy.deepcopy(other.state))

    def __len__(self):
        return len(self.state)

    def __getitem__(self, key):
        return self.state[key]

    def __setitem__(self, key, value):
        self.state[key] = value

    def append(self, item):
        return self.state.append(item)

    def pop(self, index):
        return self.state.pop(index)

    def index(self, item):
        return self.state.index(item)

class StackState(object):
    """Model of a stack's state.

    This is a visitor that processes LIR instructions and tracks
    their effects on the stack.

    Primarily, the delta values of instructions are used to determine
    their effects, but there are specific methods for stack manipulation opcodes.
    """
    def __init__(self, symbol_table):
        self.symbol_table = symbol_table
        self.assumptions = []
        self._current_scope = StateScope()
        self.scopes = [self.state]
        self.clear()

    def begin_scope(self):
        """Begin a new scope.

        Also start a new scope in the symbol table so that assumption
        values can be altered.
        """
        stack_names = self.symbol_table.lookup('_stack_names')
        self.symbol_table.begin_scope()
        if stack_names:
            self.symbol_table.add_stack_assumptions(stack_names.value)

        self.scopes.append(StateScope.copy(self.state))
        self.state = self.scopes[-1]

    def end_scope(self):
        """End the current scope in the stack state and the symbol table."""
        self.symbol_table.end_scope()
        self.scopes.pop()
        if not self.scopes:
            raise Exception('Popped the topmost scope')
        self.state = self.scopes[-1]

    @property
    def assumptions_offset(self):
        return self.state.assumptions_offset

    @assumptions_offset.setter
    def assumptions_offset(self, value):
        self.state.assumptions_offset = value

    @property
    def state(self):
        return self._current_scope

    @state.setter
    def state(self, value):
        self._current_scope = value

    @classmethod
    def copy(cls, other):
        """Instantiate from another instance of StackState."""
        self = StackState(other.symbol_table)
        self.assumptions = copy.deepcopy(other.assumptions)
        self.state = copy.deepcopy(other.state)
        self.scopes = copy.deepcopy(other.scopes)
        return self

    def change_depth(self, stack_offset, amount):
        """Change the value of the assumption at stack_offset.

        This does nothing if the stack item at stack_offset is
        not an assumption.
        """
        item = self.state[stack_offset]
        if not isinstance(item, StackItem) or not isinstance(item.op, types.Assumption):
            return
        symbol = self.symbol_table.lookup(item.op.var_name)
        symbol.value.depth += amount
        symbol.value.height -= amount

    def state_after_assumptions(self):
        return self.state[self.assumptions_offset:]

    def get_assumptions(self, assumption_name):
        """Get occurrences of assumption_name."""
        state = self.state_after_assumptions()
        ret_list = copy.deepcopy(filter(lambda i: i.is_assumption() and i.op.var_name == assumption_name, state))
        return ret_list

    def get_highest_assumption(self, assumption):
        highest, stack_index = None, None
        assumptions = self.get_assumptions(assumption.var_name)

        if assumptions:
            highest = assumptions[-1]
            stack_index = self.assumptions_offset
            for item in self.state_after_assumptions():
                if item.is_assumption() and item.op.var_name == assumption.var_name:
                    assumptions.pop(0)

                if not assumptions:
                    break

                stack_index += 1

        return highest, stack_index

    def clear(self, clear_assumptions=True):
        self.state = StateScope()
        self.scopes = [self.state]
        if clear_assumptions:
            self.assumptions = []
        self.assumptions_offset = len(self.assumptions)
        self.state[:self.assumptions_offset] = copy.deepcopy(self.assumptions)

    def state_append(self, op):
        """Append op to the stack state."""
        if isinstance(op, StackItem):
            op = copy.deepcopy(op)
        elif isinstance(op, int):
            smallint = types.small_int_opcode(op)
            if smallint:
                op = smallint()
            else:
                op = types.Push(data=op)

            op = StackItem(op)

        self.state.append(op)

    def state_pop(self, i=-1):
        if i < 0:
            i = len(self.state) - abs(i)

        op = self.state.pop(i)

        while i < self.assumptions_offset:
            self.assumptions_offset -= 1
        return op

    def add_stack_assumptions(self, assumptions):
        """Add assumed stack items to the stack."""
        assumptions = map(StackItem, assumptions)
        self.assumptions = assumptions
        self.assumptions_offset = len(self.assumptions)
        self.state[:self.assumptions_offset] = copy.deepcopy(assumptions)

    def index(self, op):
        return self.state.index(op)

    def process_instruction(self, op):
        """Process op and update the stack."""
        if not isinstance(op, (types.OpCode, types.InnerScript, types.Push)):
            return
        self.visit(op)

    def process_instructions(self, ops):
        map(self.process_instruction, ops)

    def visit(self, op):
        method = getattr(self, 'visit_%s' % op.__class__.__name__, None)
        if method:
            method(op)
        else:
            self.generic_visit(op)

    def generic_visit(self, op):
        if isinstance(op, types.SmallIntOpCode):
            return self.generic_visit_SmallIntOpCode(op)
        elif isinstance(op, types.OpCode):
            return self.generic_visit_OpCode(op)

    def generic_visit_SmallIntOpCode(self, op):
        self.state_append(op.value)

    def generic_visit_OpCode(self, op):
        delta = op.delta
        if delta > 0:
            map(lambda i: self.state_append('_delta_%s_%d' % (str(op), i)), range(delta))
        elif delta < 0:
            map(lambda i: self.state_pop(-1), range(abs(delta)))

    def visit_Push(self, op):
        self.state_append(StackItem(op))

    def visit_InnerScript(self, op):
        self.state_append(StackItem(op))


    def visit_Depth(self, op):
        self.state_append(len(self.state))

    def visit_Drop(self, op):
        self.state_pop()

    def visit_Dup(self, op):
        self.state_append(self.state[-1])

    def visit_Nip(self, op):
        self.state_pop(-2)

    def visit_Over(self, op):
        self.state_append(self.state[-2])

    def visit_Pick(self, op):
        i = int(self.state_pop())
        self.state_append(self.state[-i - 1])

    def visit_Roll(self, op):
        i = int(self.state_pop())
        val = self.state_pop(-i - 1)
        self.state_append(val)

    def visit_Rot(self, op):
        val = self.state[-3]
        self.state[-3] = self.state[-2]
        self.state[-2] = val

        val = self.state[-2]
        self.state[-2] = self.state[-1]
        self.state[-1] = val

        self.change_depth(-1, -2)
        self.change_depth(-2, 1)
        self.change_depth(-3, 1)

    def visit_Swap(self, op):
        val = self.state[-2]
        self.state[-2] = self.state[-1]
        self.state[-1] = val

        self.change_depth(-1, -1)
        self.change_depth(-2, 1)

    def visit_Tuck(self, op):
        val = self.state[-1]
        self.state.insert(len(self.state) - 2, val)

    def visit_TwoDrop(self, op):
        self.state_pop()
        self.state_pop()

    def visit_TwoDup(self, op):
        val1 = self.state[-2]
        val2 = self.state[-1]
        self.state_append(val1)
        self.state_append(val2)

    def visit_ThreeDup(self, op):
        val1 = self.state[-3]
        val2 = self.state[-2]
        val3 = self.state[-1]
        self.state_append(val1)
        self.state_append(val2)
        self.state_append(val3)

    def visit_TwoOver(self, op):
        val1 = self.state[-4]
        val2 = self.state[-3]
        self.state_append(val1)
        self.state_append(val2)

    def visit_TwoRot(self, op):
        val1 = self.state[-6]
        val2 = self.state[-5]
        del self.state[-6]
        del self.state[-5]
        self.state_append(val1)
        self.state_append(val2)

        self.change_depth(-1, -4)
        self.change_depth(-2, -4)
        self.change_depth(-3, 2)
        self.change_depth(-4, 2)
        self.change_depth(-5, 2)
        self.change_depth(-6, 2)

    def visit_TwoSwap(self, op):
        val = self.state[-4]
        self.state[-4] = self.state[-2]
        self.state[-2] = val

        val = self.state[-3]
        self.state[-3] = self.state[-1]
        self.state[-1] = val

        self.change_depth(-1, -2)
        self.change_depth(-2, -2)
        self.change_depth(-3, 2)
        self.change_depth(-4, 2)

    def visit_If(self, op):
        self.begin_scope()

    def visit_NotIf(self, op):
        self.begin_scope()

    def visit_Else(self, op):
        self.end_scope()
        self.begin_scope()

    def visit_EndIf(self, op):
        self.end_scope()
