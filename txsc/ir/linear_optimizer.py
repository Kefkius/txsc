"""Script optimizations.

Peephole optimizations in this module that affect specific sequences of
opcodes are accompanied by a comment with the following form:
    # before -> after

Here, "before" and "after" refer to opcodes. If the optimization results
in the complete removal of the "before" opcodes, an underscore is
used for "after".

Examples:
    - Replace "OP_1 OP_PICK" with "OP_OVER":
        # OP_1 OP_PICK -> OP_OVER
    - Remove "OP_0 OP_ROLL":
        # OP_0 OP_ROLL -> _

These comments are necessary so that tools/show-peephole-optimizers.py
can display the set of peephole optimizations.

Guidelines for naming peephole optimization functions:
    - If the function affects a specific type of opcode, include it
        in the name (e.g. "arithmetic", "conditional").
    - Avoid using the words "optimize", "shorten", etc.
    - Use the word "shortcut" if the optimization replaces opcodes
        with shortcut opcodes (e.g. "OP_1 OP_ADD -> OP_1ADD").

"""
import itertools

from txsc.ir import formats
from txsc.ir.instructions import LInstructions
from txsc.ir.linear_context import LinearInliner
from txsc.ir.linear_visitor import BaseLinearVisitor
import txsc.ir.linear_nodes as types

peephole_optimizers = []

_linear_optimizer_cls = None

def get_linear_optimizer_cls():
    """Get the linear optimizer class."""
    global _linear_optimizer_cls
    # Set to default if no linear optimizer is set.
    if not _linear_optimizer_cls:
        _linear_optimizer_cls = LinearOptimizer
    return _linear_optimizer_cls

def set_linear_optimizer_cls(cls):
    """Set the linear optimizer class."""
    global _linear_optimizer_cls
    _linear_optimizer_cls = cls

def peephole(func):
    """Decorator for peephole optimizers."""
    peephole_optimizers.append(func)
    return func

def permutations(nodes):
    """Return permutations of nodes."""
    return [list(i) for i in itertools.permutations(nodes, len(nodes))]


@peephole
def merge_op_and_verify(instructions):
    """Merge opcodes with a corresponding *VERIFY form.

    e.g. OP_EQUAL OP_VERIFY -> OP_EQUALVERIFY
    """
    # Opcodes in Bitcoin that are covered by this function:
    # OP_EQUAL OP_VERIFY -> OP_EQUALVERIFY
    # OP_NUMEQUAL OP_VERIFY -> OP_NUMEQUALVERIFY
    # OP_CHECKSIG OP_VERIFY -> OP_CHECKSIGVERIFY
    # OP_CHECKMULTISIG OP_VERIFY -> OP_CHECKMULTISIGVERIFY
    optimizations = []
    for op in types.iter_opcode_classes():
        if op.name.endswith('VERIFY') and op.name != 'OP_VERIFY':
            base_op = types.opcode_by_name(op.name[:-6])
            if not base_op:
                continue
            template = [base_op(), types.Verify()]
            optimizations.append((template, [op()]))

    for template, replacement in optimizations:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def alt_stack_ops(instructions):
    """Optimize alt stack operations."""
    for template, replacement in [
        # OP_TOALTSTACK OP_FROMALTSTACK -> _
        ([types.ToAltStack(), types.FromAltStack()], []),
        # OP_FROMALTSTACK OP_TOALTSTACK -> _
        ([types.FromAltStack(), types.ToAltStack()], []),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def stack_ops(instructions):
    """Optimize stack operations."""
    for template, replacement in [
        # OP_1 OP_PICK -> OP_OVER
        ([types.One(), types.Pick()], [types.Over()]),
        # OP_1 OP_ROLL OP_DROP -> OP_NIP
        ([types.One(), types.Roll(), types.Drop()], [types.Nip()]),
        # OP_0 OP_PICK -> OP_DUP
        ([types.Zero(), types.Pick()], [types.Dup()]),
        # OP_0 OP_ROLL -> _
        ([types.Zero(), types.Roll()], []),
        # OP_1 OP_ROLL OP_1 OP_ROLL -> _
        ([types.One(), types.Roll(), types.One(), types.Roll()], []),
        # OP_1 OP_ROLL -> OP_SWAP
        ([types.One(), types.Roll()], [types.Swap()]),
        # OP_NIP OP_DROP -> OP_2DROP
        ([types.Nip(), types.Drop()], [types.TwoDrop()]),
        # OP_OVER OP_OVER -> OP_2DUP
        ([types.Over(), types.Over()], [types.TwoDup()]),
        # OP_DROP OP_DROP -> OP_2DROP
        ([types.Drop(), types.Drop()], [types.TwoDrop()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def arithmetic_shortcut_ops(instructions):
    """Replace arithmetic opcodes with corresponding shortcut forms."""
    optimizations = []
    # Replace division by 2.
    # OP_2 OP_DIV -> OP_2DIV
    optimizations.append(([types.Two(), types.Div()], lambda values: [types.Div2()]))
    # Replace subtraction by 1.
    # OP_1 OP_SUB -> OP_1SUB
    optimizations.append(([types.One(), types.Sub()], lambda values: [types.Sub1()]))
    # Replace 1 * -1 with -1.
    # OP_1 OP_NEGATE -> OP_1NEGATE
    optimizations.append(([types.One(), types.Negate()], lambda values: [types.NegativeOne()]))
    # Replace addition by 1.
    # OP_1 OP_ADD -> OP_1ADD
    for permutation in permutations([types.Push(), types.One()]) + permutations([types.SmallIntOpCode(), types.One()]):
        idx = 0 if not isinstance(permutation[0], types.One) else 1
        optimizations.append((permutation + [types.Add()], lambda values, idx=idx: [values[idx], types.Add1()]))
    optimizations.append(([types.Assumption(), types.One(), types.Add()], lambda values: [values[0], types.Add1()]))
    # Replace multiplication by 2.
    # OP_2 OP_MUL -> OP_2MUL
    for permutation in permutations([types.Push(), types.Two()]) + permutations([types.SmallIntOpCode(), types.Two()]):
        idx = 0 if not isinstance(permutation[0], types.Two) else 1
        optimizations.append((permutation + [types.Mul()], lambda values, idx=idx: [values[idx], types.Mul2()]))
    optimizations.append(([types.Assumption(), types.Two(), types.Mul()], lambda values: [values[0], types.Mul2()]))


    for template, callback in optimizations:
        instructions.replace_template(template, callback, strict=False)

@peephole
def conditional_shortcut_ops(instructions):
    """Replace conditional opcodes with corresponding shortcut forms."""
    # OP_NOT OP_IF -> OP_NOTIF
    instructions.replace_template([types.Not(), types.If()], lambda values: [types.NotIf()])

@peephole
def hash_shortcut_ops(instructions):
    """Replace hash opcodes with corresponding shortcut forms."""
    for template, replacement in [
        # OP_SHA256 OP_SHA256 -> OP_HASH256
        ([types.Sha256(), types.Sha256()], [types.Hash256()]),
        # OP_SHA256 OP_RIPEMD160 -> OP_HASH160
        ([types.Sha256(), types.RipeMD160()], [types.Hash160()]),
    ]:
        callback = lambda values, replacement=replacement: replacement
        instructions.replace_template(template, callback)

@peephole
def remove_null_arithmetic(instructions):
    """Remove arithmetic operations that do nothing."""
    # Remove subtraction by 0.
    # OP_0 OP_SUB -> _
    optimizations = [([types.Zero(), types.Sub()], lambda values: [])]
    # Remove addition by 0.
    # OP_0 OP_ADD -> _
    for permutation in permutations([None, types.Zero()]):
        idx = 0 if permutation[0] is None else 1
        optimizations.append((permutation + [types.Add()], lambda values, idx=idx: [values[idx]]))

    for template, callback in optimizations:
        instructions.replace_template(template, callback)

@peephole
def remove_null_conditionals(instructions):
    """Replace empty conditionals with an op that consumes the test value."""
    # OP_ELSE OP_ENDIF -> OP_ENDIF
    instructions.replace_template([types.Else(), types.EndIf()], lambda values: [types.EndIf()])
    # OP_IF OP_ENDIF -> OP_DROP
    instructions.replace_template([types.If(), types.EndIf()], lambda values: [types.Drop()])

@peephole
def remove_trailing_verifications(instructions):
    """Remove any trailing OP_VERIFY occurrences.

    A trailing OP_VERIFY is redundant since a truthy value
    is required for a script to pass.
    """
    while len(instructions) and isinstance(instructions[-1], types.Verify):
        instructions.pop(-1)

@peephole
def use_arithmetic_ops(instructions):
    """Replace ops with more convenient arithmetic ops."""
    optimizations = []
    _two_values = permutations([types.SmallIntOpCode(), types.Push()])
    _two_values.append([types.SmallIntOpCode()] * 2)
    _two_values.append([types.Push()] * 2)

    def all_strict_nums(numbers):
        """Evaluate whether instances represent strict numbers."""
        return all(formats.is_strict_num(i) for i in map(LInstructions.instruction_to_int, numbers))

    # Use NUMNOTEQUAL if both values are numbers.
    def numnotequal_callback(values):
        if not all_strict_nums(values[0:2]):
            return values
        return values[0:2] + [types.NumNotEqual()]

    for permutation in _two_values:
        optimizations.append((permutation + [types.Equal(), types.Not()], numnotequal_callback))

    for template, callback in optimizations:
        instructions.replace_template(template, callback, strict=False)

@peephole
def use_small_int_opcodes(instructions):
    """Convert data pushes to equivalent small integer opcodes."""
    def convert_push(push):
        push = push[0]
        try:
            i = formats.bytearray_to_int(push.data)
            return [types.small_int_opcode(i)()]
        except TypeError:
            pass
        return [push]
    instructions.replace_template([types.Push()], convert_push, strict=False)

@peephole
def promote_return(instructions):
    """Place any OP_RETURN occurrence at the beginning of the script."""
    # Get the indices of all OP_RETURN occurrences.
    occurrences = instructions.find_occurrences(types.Return())
    if not occurrences or occurrences == [0]:
        return
    map(instructions.pop, reversed(occurrences))
    instructions.insert(0, types.Return())

@peephole
def commutative_operations(instructions):
    """Remove ops that change the order of commutative operations."""
    optimizations = []
    for op in [types.Add(), types.Mul(), types.BoolAnd(), types.BoolOr(),
               types.NumEqual(), types.NumEqualVerify(), types.NumNotEqual(),
               types.Min(), types.Max(),
               types.And(), types.Or(), types.Xor(), types.Equal(), types.EqualVerify(),
    ]:
        template = [types.Swap(), op]
        optimizations.append((template, lambda values: values[1:]))

    for template, callback in optimizations:
        instructions.replace_template(template, callback)


class PeepholeOptimizer(object):
    """Performs peephole optimization on the linear IR."""
    MAX_PASSES = 5
    def __init__(self, enabled=True):
        self.enabled = enabled

    def optimize(self, instructions, max_passes=-1):
        if not self.enabled:
            return
        if max_passes == -1:
            max_passes = self.MAX_PASSES

        pass_number = 0
        while 1:
            if pass_number > max_passes:
                break

            state = str(instructions)
            for func in peephole_optimizers:
                func(instructions)
            new = str(instructions)

            pass_number += 1

            if state == new:
                break

class LinearOptimizer(BaseLinearVisitor):
    """Performs optimizations on the linear IR."""
    name = 'default'
    def optimize(self, instructions):
        self.peephole_optimizer = PeepholeOptimizer(self.options.peephole_optimizations)
        if self.options.inline_assumptions:
            inliner = LinearInliner(self.symbol_table, self.options)
            inliner.inline(instructions, self.peephole_optimizer)

        self.peephole_optimizer.optimize(instructions)
