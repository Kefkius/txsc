from txsc.ir import formats
from txsc.transformer import BaseTransformer
import txsc.ir.linear_nodes as types

def op_for_int(value):
    """Get a small int or push operation for value."""
    cls = types.opcode_by_name('OP_%d'%value)
    if cls:
        return cls()
    value = formats.int_to_bytearray(value)
    return types.Push(data=value)

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
    def __init__(self, symbol_table, options=LIROptions()):
        super(BaseLinearVisitor, self).__init__()
        self.symbol_table = symbol_table
        self.options = options
