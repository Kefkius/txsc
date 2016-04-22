"""Node types for linear representation."""
import inspect
import sys

class Node(object):
    """Base class for nodes.

    Attributes:
        - name (str): Operation name.
        - delta (int): The number of stack items that this node adds (or consumes).

    """
    name = ''
    delta = 0
    def __init__(self, delta=None):
        if delta is not None:
            self.delta = delta

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and other.name == self.name)

    def __ne__(self, other):
        return not self.__eq__(other)

class Push(Node):
    name = 'push'
    def __init__(self, data=None, **kwargs):
#        if kwargs.get('delta', None) is None:
#            kwargs['delta'] = 1
        kwargs['delta'] = 1

        super(Push, self).__init__(kwargs)
        self.data = data

    def __eq__(self, other):
        return (super(Push, self).__eq__(other)
                and other.data == self.data)

    def __str__(self):
        return self.data.encode('hex')

class OpCode(Node):
    """An opcode.

    Attributes:
        - verifier (bool): Whether this opcode performs verification.

    """
    verifier = False
    def __init__(self, **kwargs):
        super(OpCode, self).__init__(kwargs)

    def __eq__(self, other):
        return (super(OpCode, self).__eq__(other)
                and other.verifier == self.verifier)

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return ('OpCode(name=%s, verifier=%s, delta=%s' % (self.name,
                self.verifier, self.delta))

class SmallIntOpCode(OpCode):
    """Small integer opcode."""
    value = 0

    def __eq__(self, other):
        return (super(SmallIntOpCode, self).__eq__(other)
                and other.value == self.value)

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

# Constants.

# TODO.
class False_(Zero):
    name = 'OP_FALSE'
class True_(One):
    name = 'OP_TRUE'
NegativeOne = _opcode('NegativeOne', 1, 'OP_1NEGATE')

# Flow control.

# TODO.
Verify = _opcode('Verify', -1, 'OP_VERIFY', verifier=True)


# Stack.

# TODO: OP_TOALTSTACK, OP_FROMALTSTACK

class IfDup(OpCode):
    name = 'OP_IFDUP'

Depth = _opcode('Depth', 1, 'OP_DEPTH')
Drop = _opcode('Drop', -1, 'OP_DROP')
Dup = _opcode('Dup', 1, 'OP_DUP')
Nip = _opcode('Nip', -1, 'OP_NIP')
Over = _opcode('Over', 1, 'OP_OVER')
Pick = _opcode('Pick', 1, 'OP_PICK')
Roll = _opcode('Roll', 0, 'OP_ROLL')
Rot = _opcode('Rot', 0, 'OP_ROT')
Swap = _opcode('Swap', 0, 'OP_SWAP')
Tuck = _opcode('Tuck', 1, 'OP_TUCK')
TwoDrop = _opcode('TwoDrop', -2, 'OP_2DROP')
TwoDup = _opcode('TwoDup', 2, 'OP_2DUP')
ThreeDup = _opcode('ThreeDup', 3, 'OP_3DUP')
TwoOver = _opcode('TwoOver', 2, 'OP_2OVER')
TwoRot = _opcode('TwoRot', 0, 'OP_2ROT')
TwoSwap = _opcode('TwoSwap', 0, 'OP_2SWAP')

# Splice.

Cat = _opcode('Cat', -1, 'OP_CAT')
Substr = _opcode('Substr', -2, 'OP_SUBSTR')
Left = _opcode('Left', -1, 'OP_LEFT')
Right = _opcode('Right', -1, 'OP_RIGHT')
Size = _opcode('Size', 1, 'OP_SIZE')

# Bitwise logic.

Invert = _opcode('Invert', 0, 'OP_INVERT')
And = _opcode('And', -1, 'OP_AND')
Or = _opcode('Or', -1, 'OP_OR')
Xor = _opcode('Xor', -1, 'OP_XOR')
Equal = _opcode('Equal', -1, 'OP_EQUAL')
EqualVerify = _opcode('EqualVerify', -2, 'OP_EQUALVERIFY', verifier=True)

# Arithmetic.

Add1 = _opcode('Add1', 0, 'OP_1ADD')
Sub1 = _opcode('Sub1', 0, 'OP_1SUB')
Mul2 = _opcode('Mul2', 0, 'OP_2MUL')
Div2 = _opcode('Div2', 0, 'OP_2DIV')
Negate = _opcode('Negate', 0, 'OP_NEGATE')
Abs = _opcode('Abs', 0, 'OP_ABS')
Not = _opcode('Not', 0, 'OP_NOT')

ZeroNotEqual = _opcode('ZeroNotEqual', 0, 'OP_0NOTEQUAL')

Add = _opcode('Add', -1, 'OP_ADD')
Sub = _opcode('Sub', -1, 'OP_SUB')
Mul = _opcode('Mul', -1, 'OP_MUL')
Div = _opcode('Div', -1, 'OP_DIV')
Mod = _opcode('Mod', -1, 'OP_MOD')
LShift = _opcode('LShift', -1, 'OP_LSHIFT')
RShift = _opcode('RShift', -1, 'OP_RSHIFT')

BoolAnd = _opcode('BoolAnd', -1, 'OP_BOOLAND')
BoolOr = _opcode('BoolOr', -1, 'OP_BOOLOR')

NumEqual = _opcode('NumEqual', -1, 'OP_NUMEQUAL')
NumEqualVerify = _opcode('NumEqualVerify', -2, 'OP_NUMEQUALVERIFY', verifier=True)
NumNotEqual = _opcode('NumNotEqual', -1, 'OP_NUMNOTEQUAL')
LessThan = _opcode('LessThan', -1, 'OP_LESSTHAN')
GreaterThan = _opcode('GreaterThan', -1, 'OP_GREATERTHAN')
LessThanOrEqual = _opcode('LessThanOrEqual', -1, 'OP_LESSTHANOREQUAL')
GreaterThanOrEqual = _opcode('GreaterThanOrEqual', -1, 'OP_GREATERTHANOREQUAL')
Min = _opcode('Min', -1, 'OP_MIN')
Max = _opcode('Max', -1, 'OP_MAX')
Within = _opcode('Within', -2, 'OP_WITHIN')

# Crypto.

RipeMD160 = _opcode('RipeMD160', 0, 'OP_RIPEMD160')
Sha1 = _opcode('Sha1', 0, 'OP_SHA1')
Sha256 = _opcode('Sha256', 0, 'OP_SHA256')
Hash160 = _opcode('Hash160', 0, 'OP_HASH160')
Hash256 = _opcode('Hash256', 0, 'OP_HASH256')
CodeSeparator = _opcode('CodeSeparator', 0, 'OP_CODESEPARATOR')
CheckSig = _opcode('CheckSig', -1, 'OP_CHECKSIG')
CheckSigVerify = _opcode('CheckSigVerify', -2, 'OP_CHECKSIGVERIFY', verifier=True)

class CheckMultiSig(OpCode):
    name = 'OP_CHECKMULTISIG'

class CheckMultiSigVerify(CheckMultiSig):
    name = 'OP_CHECKMULTISIGVERIFY'
    verifier = True


# From electrum Exchange Rates plugin.
is_op_subclass = lambda cls: (inspect.isclass(cls)
                    and issubclass(cls, OpCode)
                    and cls != OpCode)
_opcode_classes = inspect.getmembers(sys.modules[__name__], is_op_subclass)
# Opcodes by name.
opcode_classes = dict((i.name, i) for _, i in _opcode_classes)

