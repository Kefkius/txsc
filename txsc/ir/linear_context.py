from collections import defaultdict
import copy

from txsc.transformer import BaseTransformer
from txsc.ir import formats, IRError
from txsc.ir.instructions import LInstructions
from txsc.ir.linear_visitor import LIROptions, BaseLinearVisitor, StackState
import txsc.ir.linear_nodes as types

class ConditionalBranch(object):
    """A branch of a conditional.

    Attributes:
        is_truebranch (bool): Whether is represents a branch that runs if the test passes.
        start (int): The index of the first op of this branch.
        end (int): The index of the last op of this branch.
        nest_level (int): The level of nesting that this branch is at.
        orelse (ConditionalBranch): The corresponding conditional branch.

    """
    def __init__(self, is_truebranch=True, start=0, end=0, nest_level=0, orelse=None):
        self.is_truebranch = is_truebranch
        self.start = start
        self.end = end
        self.nest_level = nest_level
        self.orelse = orelse

    def __str__(self):
        return '%s(%s, %s)' % (self.is_truebranch, self.start, self.end)

    def __repr__(self):
        return str(self)

    def is_in_branch(self, idx):
        if idx >= self.start and idx <= self.end:
            return True
        return False

class LinearContextualizer(BaseLinearVisitor):
    """Populates metadata attributes of linear IR instructions."""
    def __init__(self, symbol_table, options=LIROptions()):
        super(LinearContextualizer, self).__init__(symbol_table, options)
        # {assumption_name: [occurrence_index, ...], ...}
        self.assumptions = defaultdict(list)
        # [ConditionalBranch(), ...]
        self.branches = []
        # Current level of conditional nesting.
        self.current_nest_level = 0
        self.stack = StackState()

    def log_and_raise(self, err_class, msg):
        """Log an error and raise an exception."""
        self.error(msg)
        raise err_class(msg)

    def is_before_conditionals(self, idx):
        """Get whether idx is before any conditional branches."""
        if not self.branches or idx < self.branches[0].start:
            return True
        return False

    def following_occurrences(self, assumption_name, idx):
        """Get the number of occurrences of assumption_name after idx."""
        branches = list(self.branches)
        match_any_branch = False
        if self.is_before_conditionals(idx):
            match_any_branch = True

        assumptions = self.assumptions[assumption_name]
        following = 0

        for assumption in assumptions:
            if assumption <= idx:
                continue
            if not branches:
                following += 1
            else:
                for branch in branches:
                    if not match_any_branch and branch.is_in_branch(idx):
                        continue
                    if branch.end > idx:
                        following += 1

                # Assumption beyond a conditional.
                if assumption > branches[-1].end:
                    following += 1

        return following

    def nextop(self, op):
        """Get the operation that follows op."""
        try:
            return self.instructions[op.idx + 1]
        except IndexError:
            return None

    def total_delta(self, idx):
        """Get the total delta of script operations before idx."""
        total = 0
        # Add 1 for every assumed stack item.
        total += len(self.symbol_table.lookup('_stack_names').value)
        branches = self.branches
        if self.is_before_conditionals(idx):
            total += sum(i.delta for i in self.instructions[:idx])
            return total

        idx_branch = None
        # Find the branch that idx is in.
        for branch in branches:
            if branch.is_in_branch(idx):
                if not idx_branch or idx_branch.nest_level < branch.nest_level:
                    idx_branch = branch

        # Add the deltas of instructions before the first branch in the script.
        total += sum(i.delta for i in self.instructions[:branches[0].start])
        branch_deltas = {True: [], False: []}
        for branch in branches:
            if branch == idx_branch:
                # Add the deltas of instructions before idx in its branch.
                total += sum(i.delta for i in self.instructions[branch.start:idx])
            elif branch.end < idx and (not idx_branch or branch != idx_branch.orelse):
                # Sum the deltas of conditional branches before idx.
                branch_deltas[branch.is_truebranch].append(sum(i.delta for i in self.instructions[branch.start:branch.end]))

        # If the index is after a conditional branch, check that the
        # branches before it result in the same number of stack items.
        if not sum(branch_deltas[True]) == sum(branch_deltas[False]):
            self.log_and_raise(IRError, 'Assumption encountered after uneven conditional')
        # Add the deltas from conditional branches before idx.
        total += sum(branch_deltas[True])

        return total

    def get_last_branch(self):
        """Get the last conditional branch with the current nest level."""
        for branch in reversed(self.branches):
            if branch.nest_level == self.current_nest_level:
                return branch

    def contextualize(self, instructions):
        """Perform contextualization on instructions.

        Most of these calculations will only succeed if no script execution
        must be done to place the necessary arguments into position on the stack.
        """
        if not isinstance(instructions, LInstructions):
            raise TypeError('A LInstructions instance is required')
        self.assumptions.clear()
        self.branches = []
        self.stack.clear(clear_assumptions=False)
        self.instructions = instructions

        for i, instruction in enumerate(iter(instructions)):
            instruction.idx = i
            self.visit(instruction)

        # If the current nest level is greater than 0,
        # then the script ended within a conditional branch.
        if self.current_nest_level > 0:
            self.log_and_raise(IRError, 'Script ended without ending all conditionals')

        # Validate arguments for certain opcodes.
        if not self.options.allow_invalid_comparisons:
            for instruction in self.instructions:
                if isinstance(instruction, (types.Hash160, types.RipeMD160)):
                    self.check_Hash160(instruction)
                elif isinstance(instruction, (types.Hash256, types.Sha256)):
                    self.check_Hash256(instruction)

    def check_Hash160(self, op):
        """Check that 20-byte pushes are used as RIPEMD-160 hashes."""
        data_push = self.nextop(op)
        if not isinstance(data_push, types.Push):
            return
        opcode = self.nextop(data_push)

        if not isinstance(opcode, (types.Equal, types.EqualVerify)):
            return
        if len(data_push.data) != 20:
            self.log_and_raise(IRError, 'Non-hash160 compared to the result of %s' % op.name)

    def check_Hash256(self, op):
        """Check that 32-byte pushes are used as SHA256 hashes."""
        data_push = self.nextop(op)
        if not isinstance(data_push, types.Push):
            return
        opcode = self.nextop(data_push)

        if not isinstance(opcode, (types.Equal, types.EqualVerify)):
            return
        if len(data_push.data) != 32:
            self.log_and_raise(IRError, 'Non-hash256 compared to the result of %s' % op.name)

    def visit(self, instruction):
        method = getattr(self, 'visit_%s' % instruction.__class__.__name__, None)
        if not method:
            return
        return method(instruction)

    def visit_Assumption(self, op):
        self.assumptions[op.var_name].append(op.idx)

    def visit_If(self, op):
        self.current_nest_level += 1
        self.branches.append(ConditionalBranch(is_truebranch = True, start = op.idx + 1, nest_level = self.current_nest_level))

    def visit_NotIf(self, op):
        self.current_nest_level += 1
        self.branches.append(ConditionalBranch(is_truebranch = False, start = op.idx + 1, nest_level = self.current_nest_level))

    def visit_Else(self, op):
        last_branch = self.get_last_branch()
        if not last_branch:
            self.log_and_raise(IRError, 'Else statement requires a preceding If or NotIf statement')
        last_branch.end = op.idx - 1

        new_branch = ConditionalBranch(is_truebranch = not last_branch.is_truebranch, start = op.idx + 1, nest_level = self.current_nest_level, orelse = last_branch)
        self.branches.append(new_branch)
        # Assign this branch to the orelse attribute of the preceding statement.
        last_branch.orelse = new_branch

    def visit_EndIf(self, op):
        last_branch = self.get_last_branch()
        if not last_branch:
            self.log_and_raise(IRError, 'EndIf encountered with no preceding conditional')
        last_branch.end = op.idx - 1
        self.current_nest_level -= 1

    def visit_CheckMultiSig(self, op):
        """Attempt to determine opcode arguments."""
        i = 1
        num_pubkeys = LInstructions.instruction_to_int(self.instructions[op.idx - i])
        if num_pubkeys is None:
            return

        i += 1
        i += num_pubkeys
        num_sigs = LInstructions.instruction_to_int(self.instructions[op.idx - i])
        if num_sigs is None:
            return

        i += 1
        i += num_sigs

        op.num_pubkeys = num_pubkeys
        op.num_sigs = num_sigs
        op.args = range(i)

    def visit_CheckMultiSigVerify(self, op):
        return self.visit_CheckMultiSig(op)

    def visit_IfDup(self, op):
        """Attempt to determine opcode's delta."""
        arg = LInstructions.instruction_to_int(self.instructions[op.idx - 1])
        if arg is None:
            return

        op.delta = 1 if arg else 0

    def visit_Pick(self, op):
        """Attempt to determine opcode argument."""
        arg = LInstructions.instruction_to_int(self.instructions[op.idx - 1])
        if arg is None:
            return

        op.args = [1, arg + 2]

    def visit_Roll(self, op):
        """Attempt to determine opcode argument."""
        return self.visit_Pick(op)

class LinearInliner(BaseLinearVisitor):
    """Replaces variables with stack operations."""
    def __init__(self, symbol_table, options=LIROptions()):
        super(LinearInliner, self).__init__(symbol_table, options)
        self.contextualizer = LinearContextualizer(symbol_table, options)

    def inline(self, instructions, peephole_optimizer):
        """Perform inlining of variables in instructions.

        Inlining is performed by iterating through each instruction and
        calling visitor methods. If no result is returned, the next
        instruction is visited.

        If there is a result, the instruction is replaced with that result,
        and the iteration begins again.

        Inlining ends when all instructions have been iterated over without
        any result.
        """
        if not isinstance(instructions, LInstructions):
            raise TypeError('A LInstructions instance is required')
        self.instructions = instructions

        stack_names = self.symbol_table.lookup('_stack_names')
        if stack_names:
            self.contextualizer.stack.add_stack_assumptions([types.Assumption(var_name) for var_name in stack_names.value])

        # Loop until no inlining can be done.
        while 1:
            peephole_optimizer.optimize(instructions)
            self.contextualizer.contextualize(instructions)
            inlined = False
            for i, node in enumerate(instructions):
                result = self.visit(node)
                if result is None:
                    continue
                if not isinstance(result, list):
                    result = [result]

                instructions.replace_slice(i, i+1, result)
                inlined = True
                break

            if not inlined:
                break

    def visit_consecutive_assumptions(self, assumptions):
        """Handle a row of consecutive assumptions."""
        # If the first assumption's delta is 0 and the depths are sequential,
        # then nothing needs to be done.
        if self.contextualizer.total_delta(assumptions[0].idx) - self.contextualizer.stack.assumptions_offset == 0:
            symbols = map(self.symbol_table.lookup, [i.var_name for i in assumptions])
            # http://stackoverflow.com/questions/28885455/python-check-whether-list-is-sequential-or-not
            iterator = (i.value.depth for i in reversed(symbols))
            final_item_depth = next(iterator)
            values = [(a, b) for a, b in enumerate(iterator, final_item_depth + 1)]
            if all(a == b for (a, b) in values):
                if final_item_depth == 0:
                    return []

    def bring_assumption_to_top(self, op):
        symbol = self.symbol_table.lookup(op.var_name)
        total_delta = self.contextualizer.total_delta(op.idx)

        arg = max(0, total_delta - symbol.value.height - 1)

        self.contextualizer.stack.process_instructions(self.instructions[:op.idx])
        highest, highest_stack_idx = self.contextualizer.stack.get_highest_assumption(op)
        if highest is not None:
            arg = total_delta - highest_stack_idx

        arg = self.op_for_int(arg)

        # Use OP_PICK if there are other occurrences after this one.
        opcode = types.Pick if self.contextualizer.following_occurrences(op.var_name, op.idx) > 0 else types.Roll

        return [arg, opcode()]

    def visit(self, instruction):
        method = getattr(self, 'visit_%s' % instruction.__class__.__name__, None)
        if not method:
            return
        return method(instruction)

    def visit_Assumption(self, op):
        # Detect whether there are multiple assumptions in a row.
        assumptions = [op]
        symbols = [self.symbol_table.lookup(op.var_name)]
        while 1:
            nextop = self.contextualizer.nextop(assumptions[-1])
            if nextop.__class__ is not types.Assumption:
                break
            symbol = self.symbol_table.lookup(nextop.var_name)
            if symbol.value.depth != symbols[-1].value.depth - 1:
                break

            assumptions.append(nextop)
            symbols.append(symbol)

        if len(assumptions) > 1:
            result = self.visit_consecutive_assumptions(assumptions)
            if result is not None:
                return result

        # If there are no consecutive assumptions, use opcodes to bring this assumption to the top.
        return self.bring_assumption_to_top(op)

