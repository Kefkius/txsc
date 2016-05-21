"""Structural intermediate representation for scripts."""
import ast


class ScriptOp(ast.Str):
    """Base class for nodes in this intermediate representation."""
    pass

class Script(ScriptOp):
    """A complete script."""
    _fields = ('statements',)

    def dump(self, *args):
        return ast.dump(self, *args)

class Function(ScriptOp):
    """A function."""
    _fields = ('name', 'args', 'body')

class FunctionCall(ScriptOp):
    """A call to a function."""
    _fields = ('name', 'args')

class InnerScript(ScriptOp):
    """A script contained inside a script."""
    _fields = ('statements',)

class Symbol(ScriptOp):
    """A symbol occurrence."""
    _fields = ('name')

    def __str__(self):
        return self.name

class Assignment(ScriptOp):
    """An assignment to a symbol."""
    _fields = ('name', 'value', 'type_', 'mutable')

class Push(ScriptOp):
    """A data push operation.

    Data is hex-encoded.
    """
    _fields = ('data',)

    def __int__(self):
        return int(self.data, 16) if self.data else 0

    def __str__(self):
        return self.data

    def dump(self, annotate_fields=False):
        return 'Push(%s0x%s)' % ('data=' if annotate_fields else '', self.data)

class OpCode(ScriptOp):
    """An opcode."""
    _fields = ('name',)

class VerifyOpCode(OpCode):
    """An opcode that consumes a value and fails if it is not truthy."""
    _fields = OpCode._fields + ('test',)

class UnaryOpCode(OpCode):
    """An opcode that performs a unary operation."""
    _fields = OpCode._fields + ('operand',)

class BinOpCode(OpCode):
    """An opcode that performs a binary operation."""
    _fields = OpCode._fields + ('left', 'right',)

class VariableArgsOpCode(OpCode):
    """An opcode that takes a variable number of arguments."""
    _fields = OpCode._fields + ('operands',)
