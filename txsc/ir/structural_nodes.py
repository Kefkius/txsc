"""Structural intermediate representation for scripts."""
import ast

from txsc.ir import formats

class ScriptOp(ast.Str):
    """Base class for nodes in this intermediate representation."""
    pass

class Script(ScriptOp):
    """A complete script."""
    _fields = ('statements',)

    def dump(self, *args):
        return ast.dump(self, *args)

class If(ScriptOp):
    """A conditional statement."""
    _fields = ('test', 'truebranch', 'falsebranch')

class Function(ScriptOp):
    """A function."""
    _fields = ('name', 'return_type', 'args', 'body')

class Return(ScriptOp):
    """A return statement."""
    _fields = ('value',)

class FunctionCall(ScriptOp):
    """A call to a function."""
    _fields = ('name', 'args')

class InnerScript(ScriptOp):
    """A script contained inside a script."""
    _fields = ('statements',)

class Symbol(ScriptOp):
    """A symbol occurrence."""
    _fields = ('name',)

    def __str__(self):
        return self.name

class Declaration(ScriptOp):
    """Declaration of a symbol."""
    _fields = ('name', 'value', 'type_', 'mutable')

class Assignment(ScriptOp):
    """An assignment to a symbol."""
    _fields = ('name', 'value', 'type_')

class Deletion(ScriptOp):
    """Deletion of a symbol."""
    _fields = ('name',)

class Cast(ScriptOp):
    """A casting of a value to a type."""
    _fields = ('value', 'as_type',)

class Int(ScriptOp):
    """An integer."""
    _fields = ('value',)
    @classmethod
    def coerce(cls, other):
        if isinstance(other, int):
            return cls(other)
        elif isinstance(other, Int):
            return cls(other.value)
        elif isinstance(other, Bytes):
            return cls(formats.hex_to_int(other.data))
        else:
            raise ValueError('Cannot coerce %s to Int' % other)

    def __int__(self):
        return self.value

    def __str__(self):
        return str(self.value)

class Bytes(ScriptOp):
    """A byte array.

    Data is hex-encoded.
    """
    _fields = ('data',)
    @classmethod
    def coerce(cls, other):
        if isinstance(other, str):
            return cls(other)
        elif isinstance(other, int):
            return cls(str(other))
        elif isinstance(other, Bytes):
            return cls(other.data)
        elif isinstance(other, Int):
            return cls(formats.int_to_hex(other.value))
        else:
            raise ValueError('Cannot coerce %s to Bytes' % other)

    def __int__(self):
        return int(Int.coerce(self))

    def __str__(self):
        return self.data

    def dump(self, annotate_fields=False):
        return 'Bytes(%s0x%s)' % ('data=' if annotate_fields else '', self.data)

class OpCode(ScriptOp):
    """An opcode."""
    _fields = ('name',)
    _op_args = (())

    def get_args(self):
        """Get the arguments to this opcode."""
        return [getattr(self, attr) for attr in self._op_args]

    def set_args(self, args):
        """Set the arguments to this opcode."""
        for attr, value in zip(self._op_args, args):
            setattr(self, attr, value)

class VerifyOpCode(OpCode):
    """An opcode that consumes a value and fails if it is not truthy."""
    _fields = OpCode._fields + ('test',)
    _op_args = ('test',)

class UnaryOpCode(OpCode):
    """An opcode that performs a unary operation."""
    _fields = OpCode._fields + ('operand',)
    _op_args = ('operand',)

class BinOpCode(OpCode):
    """An opcode that performs a binary operation."""
    _fields = OpCode._fields + ('left', 'right',)
    _op_args = ('left', 'right',)

class VariableArgsOpCode(OpCode):
    """An opcode that takes a variable number of arguments."""
    _fields = OpCode._fields + ('operands',)
    _op_args = ('operands',)

    def get_args(self):
        """Get the arguments to this opcode.

        Overloaded because the number of operands is unknown.
        """
        return list(self.operands)

    def set_args(self, args):
        """Set the arguments to this opcode.

        Overloaded because the number of operands is unknown.
        """
        setattr(self, 'operands', list(args))
