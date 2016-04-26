from collections import namedtuple

import txsc.ir.structural_nodes as types
from txsc.transformer import BaseTransformer, SourceVisitor

# Unary opcodes implemented as operations.
unary_ops = {
    'USub': 'OP_NEGATE',
    'Invert': 'OP_INVERT',
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


    'And': 'OP_BOOLAND',
    'Or': 'OP_BOOLOR',

    # NUMEQUAL, NUMEQUALVERIFY, NUMNOTEQUAL

    # Bitwise operations.
    'BitAnd': 'OP_AND',
    'BitOr': 'OP_OR',
    'BitXor': 'OP_XOR',

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
# TODO finish putting these in.
op_functions = [
    # Unary operations.
    OpFunc('incr', 1, 'OP_1ADD'),
    OpFunc('decr', 1, 'OP_1SUB'),
    # 2MUL, 2DIV
    OpFunc('abs', 1, 'OP_ABS'),
    # OP_NOT? , OP_0NOTEQUAL

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

    def is_script_op(self, node):
        """Return whether node is of an intermediate type."""
        return isinstance(node, types.ScriptOp)

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
        if not self.symbol_table:
            raise Exception('Cannot store name. Transformer was started without a symbol table.')
        if len(node.targets) == 1 and node.targets[0].id == '_stack':
            self.symbol_table.add_stack_assumptions([i.id for i in node.value.elts])

    def visit_Name(self, node):
        if not self.symbol_table:
            raise Exception('Cannot lookup name. Transformer was started without a symbol table.')
        symbol = self.symbol_table.lookup(node.id)
        if symbol is None:
            raise NameError('Symbol "%s" was not declared.' % node.id)
        # Assume node is a stack assumption.
        assumption = types.Assumption(name=symbol.name, depth=symbol.depth)
        return assumption

    def visit_Num(self, node):
        s = SourceVisitor.int_to_bytearray(node.n)
        return types.Push(s)

    def visit_Str(self, node):
        s = SourceVisitor.hex_to_bytearray(node.s)
        return types.Push(s)

    def visit_Assert(self, node):
        self.debug_print('visit_Assert')
        if not self.is_script_op(node.test):
            node.test = self.visit(node.test)

        unary_op = types.VerifyOpCode(name='OP_VERIFY',
                test=node.test)

        return unary_op

    def visit_UnaryOp(self, node):
        self.debug_print('visit_UnaryOp')
        if not self.is_script_op(node.operand):
            node.operand = self.visit(node.operand)

        unary_op = node.op
        if not isinstance(unary_op, types.UnaryOpCode):
            unary_op = types.UnaryOpCode(name=self.get_op_name(node.op),
                    operand=node.operand)

        return unary_op

    def visit_BinOp(self, node):
        self.debug_print('visit_BinOp')
        if not self.is_script_op(node.left):
            node.left = self.visit(node.left)
        if not self.is_script_op(node.right):
            node.right = self.visit(node.right)

        bin_op = node.op
        if not isinstance(bin_op, types.BinOpCode):
            bin_op = types.BinOpCode(name=self.get_op_name(node.op),
                    left=node.left, right=node.right)

        return bin_op

    def visit_Compare(self, node):
        self.debug_print('visit_Compare')
        if not self.is_script_op(node.left):
            node.left = self.visit(node.left)
        if not self.is_script_op(node.comparators[0]):
            node.comparators[0] = self.visit(node.comparators[0])

        # Assume one op and one comparator.
        bin_op = node.ops[0]
        if not isinstance(bin_op, types.BinOpCode):
            bin_op = types.BinOpCode(name=self.get_op_name(node.ops[0]),
                    left=node.left, right=node.comparators[0])

        return bin_op

    def visit_Call(self, node):
        """Transform function calls into their corresponding OpCodes."""
        self.debug_print('visit_Call')

        # Function name must be known.
        if node.func.id not in op_functions_dict:
            return node

        op_func = op_functions_dict[node.func.id]
        # Ensure args have been visited.
        for arg in range(len(node.args)):
            if not self.is_script_op(node.args[arg]):
                node.args[arg] = self.visit(node.args[arg])

        # Unary opcode.
        if op_func.nargs == 1:
            unary_op = types.UnaryOpCode(name = op_func.op_name,
                    operand = node.args[0])

            return unary_op
        # Binary opcode.
        elif op_func.nargs == 2:
            bin_op = types.BinOpCode(name = op_func.op_name,
                    left = node.args[0], right = node.args[1])

            return bin_op
        # Variable arguments.
        elif op_func.nargs == -1:
            op = types.VariableArgsOpCode(name = op_func.op_name,
                    operands = list(node.args))

            return op

    def format_dump(self, node, annotate_fields=True, include_attributes=False):
        if hasattr(node, 'dump'):
            return node.dump(annotate_fields)
        return super(ScriptTransformer, self).format_dump(node, annotate_fields, include_attributes)
