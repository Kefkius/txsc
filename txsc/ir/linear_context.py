from collections import defaultdict

from txsc.transformer import BaseTransformer
from txsc.ir import formats
from txsc.ir.instructions import LInstructions
import txsc.ir.linear_nodes as types

class ConditionalBranch(object):
    """A branch of a conditional.

    Attributes:
        is_truebranch (bool): Whether is represents a branch that runs if the test passes.
        start (int): The index of the first op of this branch.
        end (int): The index of the last op of this branch.

    """
    def __init__(self, is_truebranch=True, start=0, end=0):
        self.is_truebranch = is_truebranch
        self.start = start
        self.end = end

    def __str__(self):
        return '%s(%s, %s)' % (self.is_truebranch, self.start, self.end)

    def __repr__(self):
        return str(self)

    def is_in_branch(self, idx):
        if idx >= self.start and idx <= self.end:
            return True
        return False

class LinearContextualizer(BaseTransformer):
    """Populates metadata attributes of linear IR instructions."""
    def __init__(self):
        # {assumption_name: [occurrence_index, ...], ...}
        self.assumptions = defaultdict(list)
        # [ConditionalBranch(), ...]
        self.branches = []

    def following_occurrences(self, assumption_name, idx):
        """Get the number of occurrences of assumption_name after idx."""
        branches = list(self.branches)
        match_any_branch = False
        if not branches or idx <= branches[0].start:
            match_any_branch = True

        is_truebranch = None
        for branch in branches:
            if branch.is_in_branch(idx):
                is_truebranch = branch.is_truebranch
                break

        assumptions = self.assumptions[assumption_name]
        following = 0

        for assumption in assumptions:
            if assumption <= idx:
                continue
            if not branches:
                following += 1
            else:
                for branch in branches:
                    if not match_any_branch and branch.is_truebranch != is_truebranch:
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

    def contextualize(self, instructions):
        """Perform contextualization on instructions.

        Most of these calculations will only succeed if no script execution
        must be done to place the necessary arguments into position on the stack.
        """
        if not isinstance(instructions, LInstructions):
            raise TypeError('A LInstructions instance is required')
        self.assumptions.clear()
        self.branches = []
        self.instructions = instructions

        for i, instruction in enumerate(iter(instructions)):
            instruction.idx = i
            self.visit(instruction)

    def visit(self, instruction):
        method = getattr(self, 'visit_%s' % instruction.__class__.__name__, None)
        if not method:
            return
        return method(instruction)

    def visit_Assumption(self, op):
        self.assumptions[op.var_name].append(op.idx)

    def visit_If(self, op):
        self.branches.append(ConditionalBranch(is_truebranch = True, start = op.idx + 1))

    def visit_Else(self, op):
        if not self.branches:
            raise Exception('Else statement requires a preceding If statement')
        self.branches[-1].end = op.idx - 1
        self.branches.append(ConditionalBranch(is_truebranch = False, start = op.idx + 1))

    def visit_EndIf(self, op):
        self.branches[-1].end = op.idx - 1

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

class LinearInliner(BaseTransformer):
    """Replaces variables with stack operations."""
    @classmethod
    def op_for_int(self, value):
        """Get a small int or push operation for value."""
        cls = types.opcode_by_name('OP_%d'%value)
        if cls:
            return cls()
        value = formats.int_to_bytearray(value)
        return types.Push(data=value)

    def total_delta(self, idx):
        """Get the total delta of script operations before idx."""
        branches = list(self.contextualizer.branches)
        if not branches or idx <= branches[0].start:
            return sum(i.delta for i in self.instructions[:idx])

        is_truebranch = None
        for branch in branches:
            if branch.is_in_branch(idx):
                is_truebranch = branch.is_truebranch
                break

        total = sum(i.delta for i in self.instructions[:branches[0].start])
        for branch in branches:
            if branch.is_truebranch == is_truebranch and branch.start <= idx:
                if branch.end > idx:
                    total += sum(i.delta for i in self.instructions[branch.start:idx])
                    break
                else:
                    total += sum(i.delta for i in self.instructions[branch.start:branch.end])

        # If is_truebranch is None, then idx is after a conditional.
        # Add the delta of one of the conditional branches.
        # If the branches do not result in the same number of stack items,
        # then the script will have failed in StructuralVisitor.
        if is_truebranch is None:
            for branch in branches:
                if branch.is_truebranch == True:
                    total += sum(i.delta for i in self.instructions[branch.start:branch.end])

        # TODO: Fix delta calculation so that total can't be negative.
        return max(0, total)

    def inline(self, instructions, contextualizer, peephole_optimizer):
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
        self.contextualizer = contextualizer

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
        if self.total_delta(assumptions[0].idx) == 0:
            # http://stackoverflow.com/questions/28885455/python-check-whether-list-is-sequential-or-not
            iterator = (i.depth for i in reversed(assumptions))
            if all(a == b for a, b in enumerate(iterator, next(iterator) + 1)):
                return []

    def visit(self, instruction):
        method = getattr(self, 'visit_%s' % instruction.__class__.__name__, None)
        if not method:
            return
        return method(instruction)

    def visit_Assumption(self, op):
        # Detect whether there are multiple assumptions in a row.
        assumptions = [op]
        while 1:
            nextop = self.contextualizer.nextop(assumptions[-1])
            if not isinstance(nextop, types.Assumption) or nextop.depth != assumptions[-1].depth - 1:
                break
            assumptions.append(nextop)
        if len(assumptions) > 1:
            result = self.visit_consecutive_assumptions(assumptions)
            if result is not None:
                return result

        # If there are no consecutive assumptions, use opcodes to bring this assumption to the top.
        arg = self.op_for_int(self.total_delta(op.idx) + op.depth)

        # Use OP_PICK if there are other occurrences after this one.
        opcode = types.Pick if self.contextualizer.following_occurrences(op.var_name, op.idx) > 0 else types.Roll
        return [arg, opcode()]

