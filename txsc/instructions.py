from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

import txsc.linear_nodes as types

class Instructions(list):
    """Model for linear instructions."""
    @staticmethod
    def decode_number(data):
        """Decode data into an integer."""
        num = _bignum.vch2bn(data)
        # Decode num if it's a small integer.
        try:
            op = CScriptOp(num)
            return op.decode_op_n()
        except ValueError:
            pass
        return num

    @staticmethod
    def evaluate_bool(data):
        """Evaluate data as a boolean."""
        return _CastToBool(data)

    def __str__(self):
        return str(map(str, self))

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
                    and isinstance(template[i], types.Push) and isinstance(self[index + i], types.Push)
                    and template[i].data != self[index + i].data):
                equal = True

            if not equal:
                return False

        return True

    def replace(self, start, length, new_instructions):
        """Replace length instructions, starting at start."""
        values = []
        for i in range(length):
            values.append(self.pop(start))

        # If the two have the same length, attempt to substitute wildcards.
        if len(values) == len(new_instructions):
            for i, value in enumerate(values):
                if new_instructions[i] == '*':
                    new_instructions[i] = value
        new_instructions = filter(lambda i: i is not None, new_instructions)

        for j in reversed(new_instructions):
            self.insert(start, j)

    def replace_template(self, template, replacement):
        """Replace any instructions matching template with replacement."""
        idx = 0
        while 1:
            if idx >= len(self):
                break
            if (idx <= len(self) - len(template)) and self.matches_template(template, idx):
                self.replace(idx, len(template), replacement)
                idx += len(template)
            else:
                idx += 1

