"""Node types for linear representation.

Most attributes of these do not need to be supplied by the
caller. They will be determined automatically during contextualization.
"""
import inspect
import sys

class Node(object):
    """Base class for nodes.

    Attributes:
        - name (str): Operation name.
        - delta (int): The number of stack items that this node adds (or consumes).
        - idx (int): This node's index in the script.
        - comparators (tuple): Tuple of attributes that should be used when comparing
            two nodes of this type.

    """
    name = ''
    delta = 0
    idx = -1
    comparators = ('name',)
    def __init__(self, delta=None):
        if isinstance(delta, int):
            self.delta = delta

    def __eq__(self, other):
        same_values = all(getattr(other, attr) == getattr(self, attr) for attr in self.comparators)
        return isinstance(other, self.__class__) and same_values

    def __ne__(self, other):
        return not self.__eq__(other)

class Variable(Node):
    """A variable."""
    name = 'variable'
    symbol_name = ''
    comparators = Node.comparators + ('symbol_name',)
    def __init__(self, symbol_name='', **kwargs):
        super(Variable, self).__init__(**kwargs)
        self.symbol_name = symbol_name

class Assignment(Node):
    """An assignment to a variable."""
    name = 'assign'
    symbol_name = ''
    value = None
    comparators = Node.comparators + ('symbol_name', 'value',)
    def __init__(self, symbol_name='', value=None, **kwargs):
        super(Assignment, self).__init__(**kwargs)
        self.symbol_name = symbol_name
        self.value = value

class InnerScript(Node):
    """A script contained inside a script."""
    name = 'innerscript'
    ops = None
    comparators = Node.comparators + ('ops',)
    def __init__(self, ops=None, **kwargs):
        kwargs['delta'] = 1
        super(InnerScript, self).__init__(**kwargs)
        self.ops = ops if ops is not None else []

class Assumption(Node):
    """Assumption that a stack value exists."""
    name = 'assume'
    var_name = ''
    comparators = Node.comparators + ('var_name',)
    def __init__(self, var_name='', **kwargs):
        super(Assumption, self).__init__(**kwargs)
        self.var_name = var_name

    def __str__(self):
        return 'assume(%s)'%self.var_name

class Push(Node):
    name = 'push'
    comparators = Node.comparators + ('data',)
    def __init__(self, data=None, **kwargs):
        kwargs['delta'] = 1

        super(Push, self).__init__(**kwargs)
        self.data = data

    def __str__(self):
        return self.data.encode('hex')

class OpCode(Node):
    """An opcode.

    Attributes:
        - arithmetic (bool): Whether this opcode performs an arithmetic operation.
        - byte_manipulator (bool): Whether this opcode operates on the bytes of its operand(s).
        - opstr (str): A string that format() can be called on to visually represent the opcode.
        - verifier (bool): Whether this opcode performs verification.
        - args (list): The relative indices of nodes that this opcode affects.

    """
    arithmetic = False
    byte_manipulator = False
    opstr = None
    verifier = False
    args = None
    def __init__(self, **kwargs):
        super(OpCode, self).__init__(**kwargs)
        if kwargs.get('args'):
            self.args = list(kwargs['args'])

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return ('OpCode(name=%s, verifier=%s, delta=%s' % (self.name,
                self.verifier, self.delta))

    @classmethod
    def is_unary(cls):
        """Get whether this is a unary opcode."""
        return list(cls.args) == [1]

    @classmethod
    def is_binary(cls):
        """Get whether this is a binary opcode."""
        return list(cls.args) == [1, 2]

    @classmethod
    def is_ternary(cls):
        """Get whether this is a ternary opcode."""
        return list(cls.args) == [1, 2, 3]

class SmallIntOpCode(OpCode):
    """Small integer opcode."""
    value = 0
    comparators = OpCode.comparators + ('value',)

def _smallint(cls_name, num, **kwargs):
    kwargs['delta'] = 1
    kwargs['name'] = 'OP_%d' % num
    kwargs['value'] = num
    return type(cls_name, (SmallIntOpCode,), kwargs)

Zero = _smallint('Zero', 0)
One = _smallint('One', 1)
Two = _smallint('Two', 2)
Three = _smallint('Three', 3)
Four = _smallint('Four', 4)
Five = _smallint('Five', 5)
Six = _smallint('Six', 6)
Seven = _smallint('Seven', 7)
Eight = _smallint('Eight', 8)
Nine = _smallint('Nine', 9)
Ten = _smallint('Ten', 10)
Eleven = _smallint('Eleven', 11)
Twelve = _smallint('Twelve', 12)
Thirteen = _smallint('Thirteen', 13)
Fourteen = _smallint('Fourteen', 14)
Fifteen = _smallint('Fifteen', 15)
Sixteen = _smallint('Sixteen', 16)

def _opcode(cls_name, delta, name, **kwargs):
    """Create an OpCode subclass."""
    kwargs['delta'] = delta
    kwargs['name'] = name
    return type(cls_name, (OpCode,), kwargs)

def _unary_opcode(*args, **kwargs):
    """Create an OpCode subclass performs a unary operation."""
    kwargs['args'] = [1]
    return _opcode(*args, **kwargs)

def _binary_opcode(*args, **kwargs):
    """Create an OpCode subclass performs a binary operation."""
    kwargs['args'] = [1, 2]
    return _opcode(*args, **kwargs)

def _ternary_opcode(*args, **kwargs):
    """Create an OpCode subclass performs a ternary operation."""
    kwargs['args'] = [1, 2, 3]
    return _opcode(*args, **kwargs)

# Constants.

# TODO.
class False_(Zero):
    name = 'OP_FALSE'
class True_(One):
    name = 'OP_TRUE'
NegativeOne = _opcode('NegativeOne', 1, 'OP_1NEGATE')

# Flow control.

# TODO: Conditionals.
If = _unary_opcode('If', -1, 'OP_IF')
NotIf = _unary_opcode('NotIf', -1, 'OP_NOTIF')
Else = _opcode('Else', 0, 'OP_ELSE')
EndIf = _opcode('EndIf', 0, 'OP_ENDIF')
Verify = _unary_opcode('Verify', -1, 'OP_VERIFY', verifier=True)
Return = _opcode('Return', 0, 'OP_RETURN')


# Stack.

# TODO: OP_TOALTSTACK, OP_FROMALTSTACK

# TODO: delta of IfDup can only be guaranteed during execution.
IfDup = _unary_opcode('IfDup', None, 'OP_IFDUP')

Depth = _opcode('Depth', 1, 'OP_DEPTH')
Drop = _unary_opcode('Drop', -1, 'OP_DROP')
Dup = _unary_opcode('Dup', 1, 'OP_DUP')
Nip = _opcode('Nip', -1, 'OP_NIP', args=[2])
Over = _opcode('Over', 1, 'OP_OVER', args=[2])

# TODO: Relative arg indices of Pick and Roll can only be guaranteed during execution.
Pick = _opcode('Pick', 0, 'OP_PICK')
Roll = _opcode('Roll', -1, 'OP_ROLL')

Rot = _ternary_opcode('Rot', 0, 'OP_ROT')
Swap = _binary_opcode('Swap', 0, 'OP_SWAP')
# TODO: Tuck may not qualify as a binary op.
Tuck = _binary_opcode('Tuck', 1, 'OP_TUCK')
TwoDrop = _binary_opcode('TwoDrop', -2, 'OP_2DROP')
TwoDup = _binary_opcode('TwoDup', 2, 'OP_2DUP')
ThreeDup = _ternary_opcode('ThreeDup', 3, 'OP_3DUP')
TwoOver = _opcode('TwoOver', 2, 'OP_2OVER', args=[3, 4])
TwoRot = _opcode('TwoRot', 0, 'OP_2ROT', args=[5, 6])
TwoSwap = _opcode('TwoSwap', 0, 'OP_2SWAP', args=[1, 2, 3, 4])

# Splice.

Cat = _binary_opcode('Cat', -1, 'OP_CAT', byte_manipulator=True)
Substr = _ternary_opcode('Substr', -2, 'OP_SUBSTR', byte_manipulator=True)
Left = _binary_opcode('Left', -1, 'OP_LEFT', byte_manipulator=True)
Right = _binary_opcode('Right', -1, 'OP_RIGHT', byte_manipulator=True)
Size = _unary_opcode('Size', 1, 'OP_SIZE', byte_manipulator=True)

# Bitwise logic.

Invert = _unary_opcode('Invert', 0, 'OP_INVERT', arithmetic=True, opstr='~{}')
And = _binary_opcode('And', -1, 'OP_AND', arithmetic=True, opstr='{} & {}')
Or = _binary_opcode('Or', -1, 'OP_OR', arithmetic=True, opstr='{} | {}')
Xor = _binary_opcode('Xor', -1, 'OP_XOR', arithmetic=True, opstr='{} ^ {}')
Equal = _binary_opcode('Equal', -1, 'OP_EQUAL', opstr='{} == {}')
EqualVerify = _binary_opcode('EqualVerify', -2, 'OP_EQUALVERIFY', verifier=True)

# Arithmetic.

Add1 = _unary_opcode('Add1', 0, 'OP_1ADD', arithmetic=True, opstr='{}++')
Sub1 = _unary_opcode('Sub1', 0, 'OP_1SUB', arithmetic=True, opstr='{}--')
Mul2 = _unary_opcode('Mul2', 0, 'OP_2MUL', arithmetic=True, opstr='{} * 2')
Div2 = _unary_opcode('Div2', 0, 'OP_2DIV', arithmetic=True, opstr='{} / 2')
Negate = _unary_opcode('Negate', 0, 'OP_NEGATE', arithmetic=True, opstr='-{}')
Abs = _unary_opcode('Abs', 0, 'OP_ABS', arithmetic=True, opstr='|{}|')
Not = _unary_opcode('Not', 0, 'OP_NOT', arithmetic=True)

ZeroNotEqual = _unary_opcode('ZeroNotEqual', 0, 'OP_0NOTEQUAL', arithmetic=True)

Add = _binary_opcode('Add', -1, 'OP_ADD', arithmetic=True, opstr='{} + {}')
Sub = _binary_opcode('Sub', -1, 'OP_SUB', arithmetic=True, opstr='{} - {}')
Mul = _binary_opcode('Mul', -1, 'OP_MUL', arithmetic=True, opstr='{} * {}')
Div = _binary_opcode('Div', -1, 'OP_DIV', arithmetic=True, opstr='{} / {}')
Mod = _binary_opcode('Mod', -1, 'OP_MOD', arithmetic=True, opstr='{} % {}')
LShift = _binary_opcode('LShift', -1, 'OP_LSHIFT', arithmetic=True, opstr='{} << {}')
RShift = _binary_opcode('RShift', -1, 'OP_RSHIFT', arithmetic=True, opstr='{} >> {}')

BoolAnd = _binary_opcode('BoolAnd', -1, 'OP_BOOLAND', arithmetic=True, opstr='{} and {}')
BoolOr = _binary_opcode('BoolOr', -1, 'OP_BOOLOR', arithmetic=True, opstr='{} or {}')

NumEqual = _binary_opcode('NumEqual', -1, 'OP_NUMEQUAL', arithmetic=True, opstr='{} == {}')
NumEqualVerify = _binary_opcode('NumEqualVerify', -2, 'OP_NUMEQUALVERIFY', verifier=True, arithmetic=True)
NumNotEqual = _binary_opcode('NumNotEqual', -1, 'OP_NUMNOTEQUAL', arithmetic=True, opstr='{} != {}')
LessThan = _binary_opcode('LessThan', -1, 'OP_LESSTHAN', arithmetic=True, opstr='{} < {}')
GreaterThan = _binary_opcode('GreaterThan', -1, 'OP_GREATERTHAN', arithmetic=True, opstr='{} > {}')
LessThanOrEqual = _binary_opcode('LessThanOrEqual', -1, 'OP_LESSTHANOREQUAL', arithmetic=True, opstr='{} <= {}')
GreaterThanOrEqual = _binary_opcode('GreaterThanOrEqual', -1, 'OP_GREATERTHANOREQUAL', arithmetic=True, opstr='{} >= {}')
Min = _binary_opcode('Min', -1, 'OP_MIN', arithmetic=True)
Max = _binary_opcode('Max', -1, 'OP_MAX', arithmetic=True)
Within = _ternary_opcode('Within', -2, 'OP_WITHIN', arithmetic=True)

# Crypto.

RipeMD160 = _unary_opcode('RipeMD160', 0, 'OP_RIPEMD160')
Sha1 = _unary_opcode('Sha1', 0, 'OP_SHA1')
Sha256 = _unary_opcode('Sha256', 0, 'OP_SHA256')
Hash160 = _unary_opcode('Hash160', 0, 'OP_HASH160')
Hash256 = _unary_opcode('Hash256', 0, 'OP_HASH256')
CodeSeparator = _opcode('CodeSeparator', 0, 'OP_CODESEPARATOR')
CheckSig = _binary_opcode('CheckSig', -1, 'OP_CHECKSIG')
CheckSigVerify = _binary_opcode('CheckSigVerify', -2, 'OP_CHECKSIGVERIFY', verifier=True)

# TODO: Relative arg indices of CheckMultiSig and CheckMultiSigVerify can only be guaranteed during execution.
class CheckMultiSig(OpCode):
    name = 'OP_CHECKMULTISIG'
    num_pubkeys = -1
    num_sigs = -1

class CheckMultiSigVerify(CheckMultiSig):
    name = 'OP_CHECKMULTISIGVERIFY'
    verifier = True


# From electrum Exchange Rates plugin.
is_op_subclass = lambda cls: (inspect.isclass(cls)
                    and issubclass(cls, OpCode)
                    and cls != OpCode)
# Do NOT modify this.
__opcode_classes = inspect.getmembers(sys.modules[__name__], is_op_subclass)
# Opcodes by name.
opcode_classes = dict((i.name, i) for _, i in __opcode_classes)

def opcode_by_name(name):
    """Get an opcode class by name."""
    return opcode_classes.get(name)

def small_int_opcode(value):
    """Get a small int opcode by the value it pushes."""
    return opcode_by_name('OP_%d' % value)

def iter_opcode_classes():
    for cls in opcode_classes.values():
        yield cls

def get_opcodes():
    """Return the complete set of opcodes."""
    return dict(opcode_classes)

def get_default_opcodes():
    """Return the default set of opcodes."""
    return dict((i.name, i) for _, i in __opcode_classes)

def set_opcodes(classes):
    """Set opcode_classes to classes.

    Allows for extensibility via plugins.
    """
    global opcode_classes
    opcode_classes = dict(classes)

def reset_opcodes():
    """Reset opcodes to the default set."""
    set_opcodes(get_default_opcodes())
