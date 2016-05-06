import ast
from collections import namedtuple
import sys

import hexs

from txsc.ir import formats
import txsc.ir.structural_nodes as types
from txsc.transformer import BaseTransformer

if sys.version >= '3':
    import functools
    _reduce = functools.reduce
else:
    _reduce = reduce

# Unary opcodes implemented as operations.
unary_ops = {
    'USub': 'OP_NEGATE',
    'Invert': 'OP_INVERT',
    'Not': 'OP_NOT',
}

# Binary opcodes implemented as operations.
binary_ops = {
    # Arithmetic.
    'Add': 'OP_ADD',
    'Sub': 'OP_SUB',
    'Mult': 'OP_MUL',
    'Div': 'OP_DIV',
    'Mod': 'OP_MOD',
    'LShift': 'OP_LSHIFT',
    'RShift': 'OP_RSHIFT',

    # Bitwise operations.
    'BitAnd': 'OP_AND',
    'BitOr': 'OP_OR',
    'BitXor': 'OP_XOR',

    'And': 'OP_BOOLAND',
    'Or': 'OP_BOOLOR',

    # Comparisons.
    'Eq': 'OP_EQUAL',
    'NotEq': 'OP_EQUAL OP_NOT',

    'Lt': 'OP_LESSTHAN',
    'Gt': 'OP_GREATERTHAN',
    'LtE': 'OP_LESSTHANOREQUAL',
    'GtE': 'OP_GREATERTHANOREQUAL',
}


# Opcode implemented as a function call.
OpFunc = namedtuple('OpFunc', ('name', 'nargs', 'op_name'))
op_functions = [
    # Unary operations.
    OpFunc('incr', 1, 'OP_1ADD'),
    OpFunc('decr', 1, 'OP_1SUB'),
    OpFunc('abs', 1, 'OP_ABS'),
    OpFunc('size', 1, 'OP_SIZE'),

    # Binary operations.
    OpFunc('min', 2, 'OP_MIN'),
    OpFunc('max', 2, 'OP_MAX'),

    OpFunc('concat', 2, 'OP_CAT'),
    OpFunc('left', 2, 'OP_LEFT'),
    OpFunc('right', 2, 'OP_RIGHT'),


    # Crypto.
    OpFunc('ripemd160', 1, 'OP_RIPEMD160'),
    OpFunc('sha1', 1, 'OP_SHA1'),
    OpFunc('sha256', 1, 'OP_SHA256'),
    OpFunc('hash160', 1, 'OP_HASH160'),
    OpFunc('hash256', 1, 'OP_HASH256'),
    # Sig-related ops.
    OpFunc('checkSig', 2, 'OP_CHECKSIG'),
    OpFunc('checkMultiSig', -1, 'OP_CHECKMULTISIG'),

    # Ternary operations.
    OpFunc('substr', 3, 'OP_SUBSTR'),
    OpFunc('within', 3, 'OP_WITHIN'),
]

op_functions_dict = dict((i.name, i) for i in op_functions)

class ScriptTransformer(BaseTransformer):
    """Transforms input into a structural intermediate representation."""
    def __init__(self, symbol_table=None):
        super(ScriptTransformer, self).__init__()
        self.symbol_table = symbol_table

    def get_op_name(self, node):
        name = node.__class__.__name__
        if name == 'str':
            return node
        elif name in unary_ops:
            return unary_ops[name]
        elif name in binary_ops:
            return binary_ops[name]

    def visit_Module(self, node):
        node.body = map(self.visit, node.body)
        scr = types.Script(statements=filter(lambda i: i is not None, node.body))
        return scr

    def visit_Pass(self, node):
        return None

    def visit_Assign(self, node):
        """Populate symbol table."""
        if not self.symbol_table:
            raise Exception('Cannot assign value(s). Transformer was started without a symbol table.')
        if len(node.targets) > 1:
            raise Exception('Cannot assign value(s) to more than one symbol.')

        target = node.targets[0].id
        value = node.value
        sym_value = None
        sym_type = None
        # '_stack' is an invalid variable name that signifies stack assumptions.
        if target == '_stack':
            self.symbol_table.add_stack_assumptions([i.id for i in value.elts])
        else:
            value = self.visit(value)
            # Byte array value.
            if isinstance(value, types.Push):
                sym_value = formats.hex_to_list(value.data)
                sym_type = self.symbol_table.ByteArray
            # Expression value.
            else:
                sym_value = value
                sym_type = self.symbol_table.Expr
            self.symbol_table.add_symbol(target, sym_value, sym_type)

        return types.Assignment(name=target, value=value)

    def visit_Name(self, node):
        # Return the node if it's being assigned.
        if isinstance(node.ctx, ast.Store):
            return node

        if not self.symbol_table:
            raise Exception('Cannot lookup name. Transformer was started without a symbol table.')
        symbol = self.symbol_table.lookup(node.id)
        if symbol is None:
            raise NameError('Symbol "%s" was not declared.' % node.id)
        op = types.Symbol(name=symbol.name)
        return op

    def visit_Num(self, node):
        """Transform int to a hex string."""
        return self.visit(ast.Str(hex(node.n)))

    def visit_Str(self, node):
        return types.Push(hexs.format_hex(node.s))

    def visit_List(self, node):
        """Transform array of bytes to bytes."""
        return self.visit(ast.Str(''.join(node.elts)))

    def visit_Assert(self, node):
        node.test = self.visit(node.test)
        return types.VerifyOpCode(name='OP_VERIFY',
                test=node.test)

    def visit_BoolOp(self, node):
        node.values = map(self.visit, node.values)

        name = self.get_op_name(node.op)
        # Create nested boolean ops.
        op = _reduce(lambda left, right: types.BinOpCode(name=name,
            left=left, right=right), node.values)
        return op

    def visit_UnaryOp(self, node):
        node.operand = self.visit(node.operand)

        return types.UnaryOpCode(name=self.get_op_name(node.op),
                operand=node.operand)

    def visit_BinOp(self, node):
        node.left, node.right = map(self.visit, [node.left, node.right])

        return types.BinOpCode(name=self.get_op_name(node.op),
                left=node.left, right=node.right)

    def visit_Compare(self, node):
        node.left = self.visit(node.left)
        node.comparators[0] = self.visit(node.comparators[0])

        # Assume one op and one comparator.
        return types.BinOpCode(name=self.get_op_name(node.ops[0]),
                left=node.left, right=node.comparators[0])

    def visit_Call(self, node):
        """Transform function calls into their corresponding OpCodes."""
        # Function name must be known.
        if node.func.id not in op_functions_dict:
            return node

        op_func = op_functions_dict[node.func.id]
        # Ensure args have been visited.
        node.args = map(self.visit, node.args)
        # Ensure the number of args is correct.
        if op_func.nargs != -1 and len(node.args) != op_func.nargs:
            raise SyntaxError('%s takes %d arguments (%d were given)' % (op_func.name, op_func.nargs, len(node.args)))

        # Unary opcode.
        if op_func.nargs == 1:
            return types.UnaryOpCode(name = op_func.op_name,
                    operand = node.args[0])
        # Binary opcode.
        elif op_func.nargs == 2:
            return types.BinOpCode(name = op_func.op_name,
                    left = node.args[0], right = node.args[1])
        # Variable arguments.
        else:
            return types.VariableArgsOpCode(name = op_func.op_name,
                    operands = list(node.args))

    def format_dump(self, node, annotate_fields=True, include_attributes=False):
        if hasattr(node, 'dump') and not isinstance(node, types.Script):
            return node.dump(annotate_fields)
        return super(ScriptTransformer, self).format_dump(node, annotate_fields, include_attributes)
