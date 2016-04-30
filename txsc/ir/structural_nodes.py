"""Structural intermediate representation for scripts."""
import ast


class ScriptOp(ast.Str):
    """Base class for nodes in this intermediate representation."""
    pass

class Script(ScriptOp):
    """A complete script."""
    _fields = ('statements',)

class Symbol(ScriptOp):
    """A symbol occurrence."""
    _fields = ('name')

class Push(ScriptOp):
    """A data push operation.

    Data is hex-encoded.
    """
    _fields = ('data',)

    def __int__(self):
        return int(self.data, 16)

    def dump(self, annotate_fields=False):
        return 'Push(%s0x%s)' % ('data=' if annotate_fields else '', self.data)

class OpCode(ScriptOp):
    """An opcode."""
    _fields = ('name',)

class VerifyOpCode(OpCode):
    """An opcode that consumes a value and fails if it is not truthy."""
    _fields = ('name', 'test')

class UnaryOpCode(OpCode):
    """An opcode that performs a unary operation."""
    _fields = ('name', 'operand')

class BinOpCode(OpCode):
    """An opcode that performs a binary operation."""
    _fields = ('name', 'left', 'right',)

class VariableArgsOpCode(OpCode):
    """An opcode that takes a variable number of arguments."""
    _fields = ('name', 'operands')
