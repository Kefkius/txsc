import copy

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

from txsc.ir import linear_nodes
from txsc.ir import structural_nodes

# Constants for instructions type.
LINEAR = 1
STRUCTURAL = 2
def get_instructions_class(instructions_type):
    """Get the class for instructions of type instructions_type."""
    if instructions_type == LINEAR:
        return LInstructions
    elif instructions_type == STRUCTURAL:
        return SInstructions

class Instructions(object):
    """Base model for instructions."""
    @staticmethod
    def decode_number(data):
        """Decode data into an integer."""
        num = _bignum.vch2bn(data)
        # Decode num if it's a small integer.
        try:
            op = CScriptOp(num)
            return op.decode_op_n()
        except Exception:
            pass
        return num

    @staticmethod
    def evaluate_bool(data):
        """Evaluate data as a boolean."""
        return _CastToBool(data)

class LInstructions(Instructions, list):
    """Model for linear instructions."""
    ir_type = LINEAR

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

        If strict is True, then Push opcodes must push the same value that
        those in the template push.
        """
        for i in range(len(template)):
            if not template[i]:
                continue

            equal = template[i] == self[index + i]
            if strict and not equal:
                return False

            if (not equal
                    and isinstance(template[i], linear_nodes.Push) and isinstance(self[index + i], linear_nodes.Push)
                    and template[i].data != self[index + i].data):
                equal = True

            if not equal:
                return False

        return True

    def replace(self, start, length, callback):
        """Pass [start : length] instructions to callback and replace them with its result."""
        end = start + length
        values = self.copy_slice(start, end)
        self.replace_slice(start, end, callback(values))

    def replace_template(self, template, callback):
        """Call callback with any instructions matching template."""
        idx = 0
        while 1:
            if idx >= len(self):
                break
            if (idx <= len(self) - len(template)) and self.matches_template(template, idx):
                self.replace(idx, len(template), callback)
                idx += len(template)
            else:
                idx += 1

class SInstructions(Instructions):
    """Model for structural instructions."""
    ir_type = STRUCTURAL
    def __init__(self, script=structural_nodes.Script()):
        self.script = script
