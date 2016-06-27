import ast
from collections import namedtuple
import inspect
import sys

import hexs

from txsc.symbols import SymbolType
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

    'Lt': 'OP_LESSTHAN',
    'Gt': 'OP_GREATERTHAN',
    'LtE': 'OP_LESSTHANOREQUAL',
    'GtE': 'OP_GREATERTHANOREQUAL',
}


# Opcode implemented as a function call.
OpFunc = namedtuple('OpFunc', ('name', 'nargs', 'op_name'))
op_functions = [
    # Unary operations.
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

# Do NOT modify this.
__op_funcs = list(op_functions)

def get_op_functions():
    """Return the builtin opcode functions."""
    return list(op_functions)

def get_default_op_functions():
    """Return the default set of builtin opcode functions."""
    return list(__op_funcs)

def set_op_functions(funcs):
    """Set the builtin opcode functions."""
    global op_functions
    op_functions = list(funcs)

def reset_op_functions():
    set_op_functions(get_default_op_functions())

def get_op_func(name):
    """Get the OpFunc for name."""
    for i in op_functions:
        if i.name == name:
            return i

class ParsingError(Exception):
    """Exception raised when parsing fails."""
    pass

class ParsingNameError(ParsingError):
    """Exception raised when an invalid name is encountered."""
    pass

class ParsingCheckError(ParsingError):
    """Exception raised when a builtin check_*() function fails."""
    pass

class ScriptTransformer(BaseTransformer):
    """Transforms input into a structural intermediate representation."""
    @staticmethod
    def get_symbol_type(type_name):
        """Get the corresponding SymbolType constant for type_name."""
        type_names = {
            'int': SymbolType.Integer,
            'bytes': SymbolType.ByteArray,
            'expr': SymbolType.Expr,
        }
        return type_names.get(type_name)

    def __init__(self, symbol_table=None):
        super(ScriptTransformer, self).__init__()
        self.builtins = BuiltinFunctions(self)
        self.symbol_table = symbol_table

    def get_op_name(self, node):
        name = node.__class__.__name__
        if name == 'str':
            return node
        elif name in unary_ops:
            return unary_ops[name]
        elif name in binary_ops:
            return binary_ops[name]

    def visit(self, node):
        result = super(ScriptTransformer, self).visit(node)
        if result:
            result.lineno = node.lineno
        return result

    def visit_Module(self, node):
        node.body = map(self.visit_module_body_statement, node.body)
        scr = types.Script(statements=filter(lambda i: i is not None, node.body))
        return scr

    def visit_module_body_statement(self, node):
        """Wrapper for error raising."""
        try:
            return self.visit(node)
        except ParsingError as e:
            raise e.__class__(e.message, node.lineno, node.col_offset)

    def visit_Pass(self, node):
        return None

    def visit_Assign(self, node):
        """Populate symbol table."""
        if len(node.targets) > 1:
            raise ParsingError('Cannot assign value(s) to more than one symbol.')

        target = node.targets[0].id
        value = node.value
        sym_type = SymbolType.Expr

        # '_stack' is an invalid variable name that signifies stack assumptions.
        if target == '_stack':
            value = [i.id for i in value.elts]
        else:
            if isinstance(value, ast.Num):
                sym_type = SymbolType.Integer
            elif isinstance(value, ast.List):
                sym_type = SymbolType.ByteArray

            value = self.visit(value)
            # Symbol type.
            if isinstance(value, types.Symbol):
                sym_type = SymbolType.Symbol

        # Symbol declaration.
        if getattr(node, 'declaration', False):
            return types.Declaration(name=target, value=value, type_=sym_type, mutable=node.mutable)

        return types.Assignment(name=target, value=value, type_=sym_type)

    def visit_AugAssign(self, node):
        """Convenience operators."""
        left = ast.Name(id=node.target.id, ctx=ast.Load())
        left.lineno = node.lineno
        value = ast.BinOp(left=left, op=node.op, right=node.value)
        value.lineno = node.lineno
        assign = ast.Assign(targets=[node.target], value=value)
        assign.lineno = node.lineno
        assign.declaration = False
        return self.visit(assign)

    def visit_Name(self, node):
        # Return the node if it's being assigned.
        if isinstance(node.ctx, ast.Store):
            return node

        op = types.Symbol(name=node.id)
        return op

    def visit_If(self, node):
        test = self.visit(node.test)
        truebranch = self.visit(node.body)
        falsebranch = []
        if node.orelse:
            falsebranch = self.visit(node.orelse)
        return types.If(test=test, truebranch=truebranch, falsebranch=falsebranch)

    def visit_Num(self, node):
        return types.Int(node.n)

    def visit_List(self, node):
        """Transform array of bytes to bytes."""
        op = types.Bytes(hexs.format_hex(''.join(node.elts)))
        op.lineno = node.lineno
        return self.visit(op)

    def visit_Assert(self, node):
        node.test = self.visit(node.test)
        return types.VerifyOpCode(name='OP_VERIFY',
                test=node.test)

    def visit_BoolOp(self, node):
        node.values = self.map_visit(node.values)

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
        node.left, node.right = self.map_visit([node.left, node.right])

        return types.BinOpCode(name=self.get_op_name(node.op),
                left=node.left, right=node.right)

    def visit_Compare(self, node):
        node.left = self.visit(node.left)
        node.comparators[0] = self.visit(node.comparators[0])

        # Special case for NotEq (!=).
        if node.ops[0].__class__.__name__ == 'NotEq':
            binop = types.BinOpCode(name='OP_EQUAL',
                    left=node.left, right=node.comparators[0])
            return types.UnaryOpCode(name='OP_NOT', operand=binop)

        # Assume one op and one comparator.
        return types.BinOpCode(name=self.get_op_name(node.ops[0]),
                left=node.left, right=node.comparators[0])

    def visit_op_function_call(self, node):
        """Transform a function call into its corresponding OpCode."""
        op_func = get_op_func(node.func.id)
        if not op_func:
            raise ParsingNameError('No function "%s" exists.' % node.func.id)
        # Ensure args have been visited.
        node.args = self.map_visit(node.args)
        # Ensure the number of args is correct.
        if op_func.nargs != -1 and len(node.args) != op_func.nargs:
            raise ParsingError('%s() requires %d arguments (got %d)' % (op_func.name, op_func.nargs, len(node.args)))

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

    def visit_Call(self, node):
        # User-defined function.
        if self.symbol_table and self.symbol_table.lookup(node.func.id):
            symbol = self.symbol_table.lookup(node.func.id)
            if symbol.type_ != SymbolType.Func:
                raise ParsingError('Cannot call "%s" of type %s' % (node.func.id, symbol.type_))
            return types.FunctionCall(node.func.id, self.map_visit(node.args))

        # Handle "built-in" functions.
        if self.builtins.is_builtin(node.func.id):
            return self.visit(self.builtins.call_builtin(node))
        # Handle function calls that correspond to opcodes.
        if get_op_func(node.func.id):
            return self.visit_op_function_call(node)
        # Function name must be known.
        raise ParsingNameError('No function "%s" exists.' % node.func.id)

    def visit_Return(self, node):
        return types.Return(self.visit(node.value))

    # TODO Python 3 compatibility.
    def visit_FunctionDef(self, node):
        if not self.symbol_table:
            raise Exception('Cannot define function. Transformer was started without a symbol table.')

        args = node.args.args.elts
        body = self.map_visit(node.body)

        type_name = self.get_symbol_type(node.type_name)
        func_def = types.Function(node.name, type_name, args, body)
        self.symbol_table.add_function_def(func_def)
        return func_def

    def format_dump(self, node, annotate_fields=True, include_attributes=False):
        if hasattr(node, 'dump') and not isinstance(node, types.Script):
            return node.dump(annotate_fields)
        return super(ScriptTransformer, self).format_dump(node, annotate_fields, include_attributes)



class BuiltinFunctions(object):
    """Handler for "built-in" functions."""
    def __init__(self, scr_transformer):
        self.transformer = scr_transformer
        self.builtins = {}

        is_builtin = lambda method: inspect.ismethod(method) and method.__name__.startswith('builtin_')
        for k, v in inspect.getmembers(self, is_builtin):
            self.builtins[k[8:]] = v

    def visit(self, node):
        return self.transformer.visit(node)

    def map_visit(self, *args):
        return self.transformer.map_visit(*args)

    def is_builtin(self, name):
        """Get whether name is the name of a built-in function."""
        return name in self.builtins.keys()

    def call_builtin(self, node):
        """Call a built-in function."""
        result = self._call_builtin(node.func.id, node.args)
        result.lineno = node.lineno
        return result

    def _call_builtin(self, name, args):
        if not self.is_builtin(name):
            raise ValueError('Unknown function: "%s"' % name)
        return self.builtins[name](*args)

    def builtin__push(self, arg):
        """Push a value to the stack."""
        return types.Push(self.visit(arg))

    def builtin_raw(self, *args):
        """Embed a raw script within a script."""
        return types.InnerScript(self.map_visit(args))

    def builtin_markInvalid(self):
        return types.OpCode(name='OP_RETURN')

    def builtin_bytes(self, arg):
        """Cast arg to a byte array."""
        return types.Cast(self.visit(arg), SymbolType.ByteArray)

    def builtin_int(self, arg):
        """Cast arg to an integer."""
        return types.Cast(self.visit(arg), SymbolType.Integer)

    # check_*() functions.
    # These are for validation.

    def builtin_check_hash160(self, arg):
        """Check that arg is 20 bytes."""
        arg = self.visit(arg)
        if not isinstance(arg, types.Bytes):
            raise ParsingCheckError('check_hash160 failed: A byte array literal is required')
        data_len = len(arg.data) / 2
        if data_len != 20:
            raise ParsingCheckError('check_hash160 failed: Hash160s are 20 bytes (got %d)' % data_len)
        return arg

    def builtin_check_pubkey(self, arg):
        """Check that arg is 32 bytes."""
        arg = self.visit(arg)
        if not isinstance(arg, types.Bytes):
            raise ParsingCheckError('check_pubkey failed: A byte array literal is required')
        data_len = len(arg.data) / 2
        if data_len not in [33, 65]:
            raise ParsingCheckError('check_pubkey failed: Public keys are either 33 or 65 bytes (got %d)' % data_len)

        if data_len == 33 and arg.data[0:2] not in ['02', '03']:
            raise ParsingCheckError('check_pubkey failed: Compressed public keys begin with 02 or 03')
        elif data_len == 65 and arg.data[0:2] != '04':
            raise ParsingCheckError('check_pubkey failed: Uncompressed public keys begin with 04')
        return arg
