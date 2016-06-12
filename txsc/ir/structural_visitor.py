from functools import wraps
import logging

from txsc.symbols import SymbolType, ImmutableError, MultipleDeclarationsError, UndeclaredError
from txsc.transformer import BaseTransformer
from txsc.ir import formats, structural_nodes
from txsc.ir.instructions import LInstructions, SInstructions
import txsc.ir.linear_nodes as types


def returnlist(func):
    """Decorator that ensures a function returns a list."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if not isinstance(result, list):
            if result is None:
                result = []
            else:
                result = [result]
        return result
    return wrapper

class IRError(Exception):
    """Exception raised when converting SIR instructions to the LIR."""
    pass

class IRImplicitPushError(IRError):
    """Exception raised when an implicit push is encountered."""
    pass

class IRStrictNumError(IRError):
    """Exception raised when using a non-number value in an arithmetic operation."""
    pass

class IRTypeError(IRError):
    """Exception raised when using incompatible or incorrect types."""
    pass

class SIROptions(object):
    """Options for the structural intermediate representation."""
    def __init__(self, evaluate_expressions=True, implicit_pushes=True,
                 strict_num=False):
        self.evaluate_expressions = evaluate_expressions
        self.implicit_pushes = implicit_pushes
        self.strict_num = strict_num

class BaseStructuralVisitor(BaseTransformer):
    """Base class for structural visitors."""
    symbol_table = None
    def __init__(self, options=SIROptions()):
        super(BaseStructuralVisitor, self).__init__()
        self.options = options

    def require_symbol_table(self, purpose=None):
        """Raise an exception if no symbol table is present."""
        if not purpose:
            purpose = 'process'
        if not self.symbol_table:
            raise Exception('Cannot %s: No symbol table was supplied to %s.' % (purpose, self.__class__.__name__))

    def visit_Cast(self, node):
        value = node.value
        if isinstance(value, structural_nodes.Symbol):
            self.require_symbol_table('cast value')
            value = self.symbol_table.lookup(value.name).value

        line_number = value.lineno
        value = self.visit(value)
        return_value = None

        if node.as_type == SymbolType.Integer:
            return_value = structural_nodes.Int.coerce(value)
        elif node.as_type == SymbolType.ByteArray:
            return_value = structural_nodes.Bytes.coerce(value)

        if return_value:
            return_value.lineno = line_number
        return return_value

    def cast_return_type(self, node, as_type):
        """Return node implicitly casted as as_type.

        This does not perform casting of types that have equal
        specificity (e.g. integers are not implicitly casted to byte arrays).
        """
        value_type = SInstructions.get_symbol_type_for_node(node)
        line_number = node.lineno
        return_value = None
        if value_type == as_type:
            return_value = node
        if as_type == SymbolType.Expr:
            return_value = node

        if return_value:
            return_value.lineno = line_number
            return return_value
        raise IRTypeError('Function returned type %s (expected %s)' % (value_type, as_type))

    def check_types(self, node):
        """Check the operand types of node."""
        if not isinstance(node, structural_nodes.OpCode):
            return
        args = node.get_args()
        if any(isinstance(arg, structural_nodes.Symbol) for arg in args):
            self.require_symbol_table('process operands')
        for i, arg in enumerate(args):
            if isinstance(arg, structural_nodes.Symbol):
                args[i] = self.symbol_table.lookup(arg.name).value

        if SInstructions.is_arithmetic_op(node):
            for arg in args:
                if isinstance(arg, structural_nodes.Bytes):
                    msg = 'Byte array %s used in arithmetic operation' % (arg)
                    self.warning(msg, node.lineno)
        elif SInstructions.is_byte_string_op(node):
            for arg in args:
                if isinstance(arg, structural_nodes.Int):
                    msg = 'Integer %s used in byte string operation' % (arg)
                    self.error(msg, node.lineno)
                    raise IRTypeError(msg, node.lineno)

    def parse_Assignment(self, node):
        """Parse an assignment statement into a more direct one."""
        self.require_symbol_table('assign value')

        type_ = node.type_
        value = node.value
        # Symbol value.
        if type_ == SymbolType.Symbol:
            other = self.symbol_table.lookup(value.name)
            type_ = other.type_
            value = other.value
        result = structural_nodes.Assignment(node.name, value, type_)
        result.lineno = node.lineno
        return result

    def add_Assignment(self, node):
        """Add an assignment to the symbol table."""
        self.require_symbol_table('assign value')

        # Prevent infinite recursion by substituting.
        # If the value being assigned is an operation and any argument to
        # the operation is the symbol being assigned to,
        # substitute the symbol's current value in the argument's place.
        if isinstance(node.value, structural_nodes.OpCode):
            if any(isinstance(i, structural_nodes.Symbol) and i.name == node.name for i in node.value.get_args()):
                old_value = self.symbol_table.lookup(node.name).value
                new_args = node.value.get_args()

                for idx, arg in enumerate(new_args):
                    if isinstance(arg, structural_nodes.Symbol) and arg.name == node.name:
                        new_args[idx] = old_value

                node.value.set_args(new_args)

        try:
            self.symbol_table.add_symbol(node.name, node.value, node.type_)
        except (ImmutableError, UndeclaredError) as e:
            raise IRError(e.message)

    def add_Declaration(self, node):
        """Add a declaration to the symbol table."""
        self.require_symbol_table('declare symbol')

        type_ = node.type_
        value = node.value
        # '_stack' is an invalid variable name that signifies stack assumptions.
        if node.name == '_stack':
            self.symbol_table.add_stack_assumptions(value)
            return
        else:
            # Symbol value.
            if type_ == SymbolType.Symbol:
                other = self.symbol_table.lookup(value.name)
                type_ = other.type_
                value = other.value

        try:
            self.symbol_table.add_symbol(node.name, value, type_, node.mutable, declaration=True)
        except MultipleDeclarationsError as e:
            raise IRError(e.message)

    def add_FunctionCall(self, node):
        """Bind arguments to node's formal parameters."""
        self.require_symbol_table('process function call')

        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('No function "%s" exists.' % node.name)
        elif symbol.type_ != SymbolType.Func:
            raise IRTypeError('Cannot call "%s" of type %s' % (node.name, symbol.type_))

        func = symbol.value
        if len(func.args) != len(node.args):
            raise IRError('Function "%s" requires %d argument(s) (got %d)' % (func.name, len(func.args), len(node.args)))

        self.symbol_table.begin_scope()
        # Bind arguments to formal parameters.
        for param, arg in zip(func.args, node.args):
            # TODO use a specific symbol type instead of expression.
            self.symbol_table.add_symbol(name=param.id, value=arg, type_ = SymbolType.Expr, declaration=True)

        return func

class StructuralVisitor(BaseStructuralVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None):
        # Whether we've finished visiting a conditional that results in a different
        # number of stack items depending on whether or not it is true.
        self.after_uneven_conditional = False
        self.symbol_table = symbol_table
        self.script = node
        self.instructions = LInstructions(self.visit(node.script))
        return self.instructions

    def visit(self, node):
        try:
            return super(StructuralVisitor, self).visit(node)
        except IRError as e:
            lineno = node.lineno
            if len(e.args) > 1:
                lineno = e.args[1]
            raise e.__class__(e.args[0], lineno)

    @returnlist
    def visit_list(self, node):
        return self.visit(structural_nodes.Bytes(''.join(node)))

    @returnlist
    def visit_Script(self, node):
        return_value = []
        for stmt in node.statements:
            if SInstructions.is_push_operation(stmt):
                msg = 'Implicit push of %s %s' % (stmt.__class__.__name__, SInstructions.format_op(stmt))
                if not self.options.implicit_pushes:
                    self.error(msg, stmt.lineno)
                    raise IRImplicitPushError(msg, stmt.lineno)
                else:
                    self.warning(msg, stmt.lineno)
            return_value.extend(self.visit(stmt))
        return return_value

    @returnlist
    def visit_InnerScript(self, node):
        ops = []
        for stmt in node.statements:
            ops.extend(self.visit(stmt))
        return types.InnerScript(ops=ops)

    @returnlist
    def visit_Declaration(self, node):
        self.add_Declaration(node)

    @returnlist
    def visit_Assignment(self, node):
        assignment = self.parse_Assignment(node)

        if isinstance(assignment.value, (structural_nodes.Int, structural_nodes.Bytes)):
            if not formats.is_strict_num(int(assignment.value)):
                msg = 'Assignment value to %s is longer than 4 bytes: 0x%x' % (assignment.name, assignment.value)
                if self.options.strict_num:
                    self.error(msg, assignment.lineno)
                    raise IRStrictNumError(msg)
                else:
                    self.warning(msg, assignment.lineno)

        self.add_Assignment(assignment)
        return None

    @returnlist
    def visit_Deletion(self, node):
        self.require_symbol_table('delete symbol')

        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('Symbol "%s" was not declared.' % node.name)
        if symbol.type_ != SymbolType.StackItem:
            raise IRError('Only assumed stack items can be deleted.')

        return types.Deletion(symbol.name, symbol.value)

    @returnlist
    def visit_Symbol(self, node):
        self.require_symbol_table('process symbol')

        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('Symbol "%s" was not declared.' % node.name)

        value = symbol.value
        type_ = symbol.type_
        # Add an assumption for the stack item.
        if type_ == SymbolType.StackItem:
            # Fail if there are assumptions after a conditional and the conditional branches do not result in the
            # same number of stack items.
            if self.after_uneven_conditional:
                raise IRError("Conditional branches must result in the same number of stack values, or assumptions afterward are not supported.")
            return types.Assumption(symbol.name, value)
        # Push the bytes of the byte array.
        elif type_ in [SymbolType.ByteArray, SymbolType.Integer]:
            return self.visit(value)
        # If the type is an expression, then StructuralOptimizer could not simplify it.
        # Evaluate the expression as if it were encountered in the structural IR.
        elif type_ == SymbolType.Expr:
            return self.visit(value)

    @returnlist
    def visit_If(self, node):
        test = self.visit(node.test)
        truebranch = self.visit(node.truebranch)
        falsebranch = []
        ops = test + [types.If()]

        ops.extend(truebranch)
        if node.falsebranch:
            falsebranch = self.visit(node.falsebranch)
            if falsebranch:
                ops.extend([types.Else()] + falsebranch)
        ops.append(types.EndIf())

        if sum([i.delta for i in truebranch]) != sum([i.delta for i in falsebranch]):
            self.after_uneven_conditional = True
        return ops

    @returnlist
    def visit_Push(self, node):
        return self.visit(node.expr)

    @returnlist
    def visit_Int(self, node):
        smallint = types.small_int_opcode(int(node))
        if smallint:
            return smallint()
        else:
            return types.Push(formats.int_to_bytearray(node.value))

    @returnlist
    def visit_Bytes(self, node):
        try:
            return types.small_int_opcode(int(node.data, 16))()
        except (TypeError, ValueError):
            return types.Push(formats.hex_to_bytearray(node.data))

    @returnlist
    def visit_OpCode(self, node):
        op = types.opcode_by_name(node.name)()
        return op

    @returnlist
    def visit_VerifyOpCode(self, node):
        return_value = self.visit(node.test)
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_UnaryOpCode(self, node):
        if SInstructions.is_arithmetic_op(node) and isinstance(node.operand, (structural_nodes.Int, structural_nodes.Bytes)):
            if not formats.is_strict_num(int(node.operand)):
                msg = 'Input value to %s is longer than 4 bytes: 0x%x' % (node.name, node.operand)
                if self.options.strict_num:
                    self.error(msg, node.lineno)
                    raise IRStrictNumError(msg)
                else:
                    self.warning(msg, node.lineno)
        return_value = self.visit(node.operand)
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_BinOpCode(self, node):
        # Check for values longer than 4 bytes.
        if SInstructions.is_arithmetic_op(node):
            operands = [node.left, node.right]
            if all(isinstance(i, (structural_nodes.Int, structural_nodes.Bytes)) for i in operands):
                valid = [formats.is_strict_num(int(i)) for i in operands]
                if False in valid:
                    msg = 'Input value to %s is longer than 4 bytes: 0x%x' % (node.name, operands[valid.index(False)])
                    if self.options.strict_num:
                        self.error(msg, node.lineno)
                        raise IRStrictNumError(msg)
                    else:
                        self.warning(msg, node.lineno)

        return_value = self.visit(node.left)
        return_value.extend(self.visit(node.right))
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_VariableArgsOpCode(self, node):
        return_value = []
        for arg in node.operands:
            return_value.extend(self.visit(arg))
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_FunctionCall(self, node):
        raise IRError("Function call could not be evaluated")

    @returnlist
    def visit_Function(self, node):
        for stmt in node.body:
            if SInstructions.is_push_operation(stmt):
                msg = 'Functions cannot push values to the stack'
                self.error(msg, stmt.lineno)
                raise IRImplicitPushError(msg, stmt.lineno)
