from collections import defaultdict
import copy

from txsc.symbols import ScopeType
from txsc.ir import formats
import txsc.ir.linear_nodes as types
from txsc.ir.linear_visitor import op_for_int

class AltStackItem(object):
    """Alt stack item.

    Attributes:
        initial value: Value that the variable was declared with.
        assignments (int): Number of assignments to the variable.
        variable_index (int): Index of the variable in the alt stack.
        assigned_in_conditional (bool): Whether the variable was assigned to within a conditional.
        is_assumption (bool): Whether the variable is an assumed stack item.
    """
    def __init__(self):
        self.initial_value = None
        self.assignments = 0
        self.variable_index = None
        self.assigned_in_conditional = False
        self.is_assumption = False

    def is_immutable(self):
        """Return whether this item can be treated as immutable."""
        return self.assignments == 1

    def requires_alt_stack(self):
        """Return whether this item must be manipulated using the alt stack."""
        if self.is_assumption:
            return True
        return self.assigned_in_conditional and not self.is_immutable()

class AltStackManager(object):
    """Keeps track of and manipulates variable locations on the alt stack."""
    def __init__(self, options):
        self.alt_stack_items = defaultdict(AltStackItem)
        self.options = options

    def analyze(self, instructions, stack_names=None):
        """Analyze instructions.

        Args:
            instructions (LInstructions): Script instructions.
            stack_names (dict): A dict of the stack names which should be
                accessed like user-defined variables and their depths.

        Returns:
            The operations needed to set up the alt stack.
        """
        self.alt_stack_items.clear()
        if stack_names and self.options.use_altstack_for_assumptions:
            for i, (stack_name, depth) in enumerate(stack_names.items()):
                item = AltStackItem()
                item.is_assumption = True
                item.variable_index = i
                # Push the item to the alt stack.
                item.initial_value = [op_for_int(depth), types.Roll()]
                self.alt_stack_items[stack_name] = item

        conditional_level = 0
        for i in instructions:
            # Track the conditional nesting level.
            if isinstance(i, types.If):
                conditional_level += 1
            elif isinstance(i, types.EndIf):
                conditional_level -= 1

            if isinstance(i, types.Assignment):
                item = self.alt_stack_items[i.var_name]

                # Record if the assignment is within a conditional.
                if conditional_level > 0:
                    item.assigned_in_conditional = True

                item.assignments += 1
                # Assign the item's index and initial value.
                if item.variable_index is None:
                    item.variable_index = len(self.alt_stack_items)
                    item.initial_value = i.value

        # Get rid of unused variable indices.
        items = filter(lambda item: item[1].requires_alt_stack(), self.alt_stack_items.items())
        indices = {k: v.variable_index for k, v in items}
        # max() will raise an exception if an empty collection is passed.
        all_indices = range(0, max(indices.values()) + 1) if indices else []
        unused_indices = sorted(filter(lambda i: i not in indices.values(), all_indices))

        while unused_indices:
            index = unused_indices.pop(0)
            # Decrease every index greater than the unused index by 1.
            for k in indices.keys():
                if indices[k] > index:
                    indices[k] -= 1
        # Assign the new indices (or None) to each alt stack item.
        for k, v in self.alt_stack_items.items():
            v.variable_index = indices.get(k, None)

        # Return the ops used to set up the initial alt stack.
        ops = []
        for item in sorted(self.alt_stack_items.values(), key = lambda i: i.variable_index):
            # Omit if the item doesn't require alt stack allocation.
            if not item.requires_alt_stack():
                continue
            symbol_ops = []
            val = item.initial_value
            symbol_ops.extend(val)
            symbol_ops.append(types.ToAltStack())

            ops.extend(symbol_ops)

        return ops

    def get_values_after_item(self, item):
        """Get the number of alt stack items after item."""
        indices = filter(lambda i: i.variable_index is not None and i.variable_index > item.variable_index, self.alt_stack_items.values())
        return len(indices)

    def _repeat_ops(self, classes, count):
        """Repeat instantiation of classes count times.

        This is used to avoid multiplication of lists.
        """
        result = []
        for i in range(count):
            ops = [cls() for cls in classes]
            result.extend(ops)
        return result

    def get_variable(self, op, is_last_occurrence=False):
        """Bring name to the top of the stack.

        If is_last_occurrence is True, the variable will not be pushed
        back onto the alt stack.

        Returns:
            The operations needed to bring op to the top of the stack,
                or None if the value can be found without the alt stack.
        """
        name = op.var_name
        item = self.alt_stack_items[name]
        if not item.requires_alt_stack():
            return None

        values_after = self.get_values_after_item(item)
        ops = []
        # Pop the other items off the alt stack.
        ops.extend(self._repeat_ops([types.FromAltStack], values_after))
        # Pop the actual variable from the alt stack.
        ops.extend([types.FromAltStack()])
        replacement_ops = [types.ToAltStack]
        if not is_last_occurrence:
            ops.extend([types.Dup(), types.ToAltStack()])
            replacement_ops.insert(0, types.Swap)
        # Push the variables back onto the alt stack.
        ops.extend(self._repeat_ops(replacement_ops, values_after))

        return ops

    def set_variable(self, op):
        """Set the top stack item in name's place.

        Returns:
            The operations needed to set the value of op,
                or None if no operations are required.
        """
        name = op.var_name
        item = self.alt_stack_items[name]
        if not item.requires_alt_stack():
            return None

        values_after = self.get_values_after_item(item)
        ops = op.value
        # Pop the other items off the alt stack.
        ops.extend(self._repeat_ops([types.FromAltStack], values_after))
        # Drop the old value.
        ops.extend([types.FromAltStack(), types.Drop()])
        # Bring the value on the main stack to the top.
        arg = op_for_int(values_after)
        ops.extend([arg, types.Roll()])
        # Set the value.
        ops.append(types.ToAltStack())
        # Push the variables back onto the alt stack.
        ops.extend(self._repeat_ops([types.ToAltStack], values_after))

        return ops

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
    def __init__(self, assumptions_offset=0, state=None, altstack=None):
        self.assumptions_offset = assumptions_offset
        self.state = state if state is not None else []
        self.altstack = altstack if altstack is not None else []

    @classmethod
    def copy(cls, other):
        return cls(assumptions_offset=other.assumptions_offset,
                   state=copy.deepcopy(other.state),
                   altstack=copy.deepcopy(other.altstack))

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

    def begin_scope(self, scope_type=ScopeType.General):
        """Begin a new scope.

        Also start a new scope in the symbol table so that assumption
        values can be altered.
        """
        stack_names = self.symbol_table.lookup('_stack_names')
        self.symbol_table.begin_scope(scope_type)
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
        elif isinstance(op, str):
            op = StackItem(types.Push(data=op))

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
        if not isinstance(op, (types.Assignment, types.OpCode, types.InnerScript, types.Push)):
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
        # Pop mutated values.
        map(lambda i: self.state_pop(-1), range(len(op.args)))
        # Add stack markers for mutated values.
        for i in range(abs(abs(op.delta) - len(op.args))):
            self.state_append('_result_of_%s' % op.name)

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
        self.begin_scope(ScopeType.Conditional)

    def visit_NotIf(self, op):
        self.begin_scope(ScopeType.Conditional)

    def visit_Else(self, op):
        self.end_scope()
        self.begin_scope(ScopeType.Conditional)

    def visit_EndIf(self, op):
        self.end_scope()

    def visit_Assignment(self, op):
        symbol = self.symbol_table.lookup(op.var_name)
        symbol.value = op.value

    def visit_ToAltStack(self, op):
        item = self.state_pop()
        self.state.altstack.append(item)

    def visit_FromAltStack(self, op):
        item = self.state.altstack.pop()
        self.state_append(item)
