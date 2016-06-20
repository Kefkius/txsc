
from txsc.ir import formats
from txsc.transformer import BaseTransformer
import txsc.ir.linear_nodes as types

class LIROptions(object):
    """Options for the linear intermediate representation.

    Attributes:
        inline_assumptions (bool): Whether to inline assumptions as stack operations.
        peephole_optimizations (bool): Whether to perform peephole optimizations.

    """
    def __init__(self, inline_assumptions=True,
                 peephole_optimizations=True):
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
        self.symbol_table = symbol_table
        self.options = options
