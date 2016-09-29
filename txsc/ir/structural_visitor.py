import copy
from functools import wraps
import logging

from txsc.symbols import ScopeType, SymbolType, ImmutableError, MultipleDeclarationsError, UndeclaredError
from txsc.transformer import BaseTransformer
from txsc.ir import formats, structural_nodes, IRError, IRImplicitPushError, IRStrictNumError, IRTypeError
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


class SIROptions(object):
    """Options for the structural intermediate representation.

    Attributes:
        evaluate_expressions (bool): Whether to evaluate constant expressions.
        implicit_pushes (bool): Whether to allow implicit pushing of values to the stack.
        strict_num (bool): Whether to fail if values longer than 4 bytes are treated as integers.

    """
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
            return_value = SInstructions.coerce(value, structural_nodes.Int)
        elif node.as_type == SymbolType.ByteArray:
            return_value = SInstructions.coerce(value, structural_nodes.Bytes)

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

        lineno = node.lineno
        type_ = node.type_
        value = node.value
        # Symbol value.
        if type_ == SymbolType.Symbol:
            other = self.symbol_table.lookup(value.name)
            type_ = other.type_
            value = other.value
        # Function value.
        elif type_ == SymbolType.Func:
            raise IRError('Cannot assign function to symbol')
        node = structural_nodes.Assignment(node.name, value, type_)
        node.lineno = lineno

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

        return node

    def add_Assignment(self, node):
        """Add an assignment to the symbol table."""
        self.require_symbol_table('assign value')

        if node.type_ == SymbolType.StackItem:
            raise IRError('Cannot assign assumed stack item to symbol')

        try:
            self.symbol_table.add_symbol(node.name, node.value, node.type_)
        except (ImmutableError, UndeclaredError) as e:
            raise IRError(e.message)

    def parse_Declaration(self, node):
        self.require_symbol_table('declare symbol')
        if node.name == '_stack':
            return node

        lineno = node.lineno
        type_ = node.type_
        value = node.value
        # Symbol value.
        if type_ == SymbolType.Symbol:
            other = self.symbol_table.lookup(value.name)
            if other.type_ != SymbolType.StackItem:
                type_ = other.type_
                value = other.value
        # Function value.
        elif type_ == SymbolType.Func:
            raise IRError('Cannot assign function to symbol')
        node = structural_nodes.Declaration(node.name, value, type_, node.mutable)
        node.lineno = lineno
        return node

    def add_Declaration(self, node):
        """Add a declaration to the symbol table."""
        self.require_symbol_table('declare symbol')

        # '_stack' is an invalid variable name that signifies stack assumptions.
        if node.name == '_stack':
            self.symbol_table.add_stack_assumptions(node.value)
            return

        try:
            self.symbol_table.add_symbol(node.name, node.value, node.type_, node.mutable, declaration=True)
        except MultipleDeclarationsError as e:
            raise IRError(e.message)

    def add_FunctionCall(self, node):
        """Get a function."""
        self.require_symbol_table('process function call')

        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('No function "%s" exists.' % node.name)
        elif symbol.type_ != SymbolType.Func:
            raise IRTypeError('Cannot call "%s" of type %s' % (node.name, symbol.type_))

        func = symbol.value
        # Validate the number of arguments.
        if len(func.args) != len(node.args):
            raise IRError('Function "%s" requires %d argument(s) (got %d)' % (func.name, len(func.args), len(node.args)))

        func = FunctionVisitor().transform(copy.deepcopy(func), node.args, self.symbol_table)
        return func

    def bind_args(self, args, func):
        """Bind args to func's formal parameters."""
        self.symbol_table.begin_scope(scope_type=ScopeType.Function)
        for param, arg in zip(func.args, args):
            self.symbol_table.add_symbol(name=param.id, value=arg, type_ = SymbolType.FuncArg, declaration=True)

        return (args, func)

class SymbolVisitor(BaseStructuralVisitor):
    """Substitutes symbols with their values."""
    def __init__(self, substitute_assumptions=False):
        self.substitute_assumptions = substitute_assumptions

    def transform(self, node, symbol_table):
        self.symbol_table = symbol_table
        return self.visit(node)

    def visit_Symbol(self, node):
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('Symbol "%s" was not declared.' % node.name)
        if symbol.type_ == SymbolType.StackItem and not self.substitute_assumptions:
            return node
        return symbol.value

class FunctionDefinitionVisitor(BaseStructuralVisitor):
    """Validates function definitions."""
    def __init__(self, *args, **kwargs):
        super(FunctionDefinitionVisitor, self).__init__(*args, **kwargs)
        # Whether a return statement has been encountered.
        self.has_returned = False

    def transform(self, node, symbol_table):
        self.has_returned = False
        return self.visit(node)

    def visit_Function(self, node):
        for stmt in node.body:
            if SInstructions.is_push_operation(stmt):
                msg = 'Functions cannot push values to the stack'
                self.error(msg, stmt.lineno)
                raise IRImplicitPushError(msg, stmt.lineno)
            self.visit(stmt)

        if not self.has_returned:
            raise IRError('Functions must have a return statement')

    def visit_Return(self, node):
        """Ensure that only one return statement is present."""
        if self.has_returned:
            raise IRError('Functions can only have one return statement')
        self.has_returned = True

class FunctionVisitor(BaseStructuralVisitor):
    """Handles symbol declarations in function calls."""
    def __init__(self, *args, **kwargs):
        super(FunctionVisitor, self).__init__(*args, **kwargs)
        self.local_vars = {}

    def get_parameter_index(self, name):
        """Get the index of the named parameter."""
        ids = [param.id for param in self.parameters]
        try:
            return ids.index(name)
        except Exception:
            return None

    def mangle_name(self, name):
        """Mangle a name with the id of the function."""
        return '%s_%s' % (name, id(self.func))

    def transform(self, node, args, symbol_table):
        self.func = node
        self.symbol_table = symbol_table
        self.parameters = node.args
        self.args = args

        symbol_table.begin_scope(scope_type=ScopeType.Function)
        result = self.visit(node)
        symbol_table.end_scope()
        return result

    def visit_Declaration(self, node):
        node.value = self.visit(node.value)
        node.type_ = SInstructions.get_symbol_type_for_node(node.value)
        node = self.parse_Declaration(node)

        name = self.mangle_name(node.name)
        self.local_vars[node.name] = name
        node.name = name
        self.add_Declaration(node)

        return node

    def visit_Assignment(self, node):
        node.value = self.visit(node.value)
        node.type_ = SInstructions.get_symbol_type_for_node(node.value)
        node = self.parse_Assignment(node)
        if node.name in self.local_vars:
            node.name = self.local_vars[node.name]
        self.add_Assignment(node)

        return node

    def visit_Symbol(self, node):
        idx = self.get_parameter_index(node.name)
        # Replace formal parameter with argument.
        if idx is not None:
            return self.args[idx]

        # Replace the symbol's name with its mangled name.
        if node.name in self.local_vars:
            node.name = self.local_vars[node.name]
        result = SymbolVisitor().transform(node, self.symbol_table)
        if result != node:
            result.lineno = node.lineno
            return result

        return node

class StructuralVisitor(BaseStructuralVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None):
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
    def visit_Cast(self, node):
        return super(StructuralVisitor, self).visit_Cast(node)

    @returnlist
    def visit_Script(self, node):
        return_value = []
        for stmt in node.statements:
            if not isinstance(stmt, structural_nodes.Push) and SInstructions.is_push_operation(stmt):
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
        node = self.parse_Declaration(node)
        result = None
        # Names that start with an underscore are used internally.
        if not node.name.startswith('_'):
            node.value = self.visit(node.value)
            result = types.Declaration(node.name, node.value, node.type_, node.mutable)

        self.add_Declaration(node)
        return result

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

        assignment.value = self.visit(assignment.value)
        result = None
        # Names that start with an underscore are used internally.
        if not assignment.name.startswith('_'):
            result = types.Assignment(assignment.name, assignment.value, assignment.type_)
        return result

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
            return types.Assumption(symbol.name)
        else:
            return types.Variable(node.name)

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
        func = self.add_FunctionCall(node)
        args = node.args

        body = copy.deepcopy(func.body)
        ops = []
        for i in body:
            ops.extend(self.visit(i))
        return ops

    @returnlist
    def visit_Function(self, node):
        # Validate the function definition.
        FunctionDefinitionVisitor().transform(node, self.symbol_table)
        self.symbol_table.add_function_def(node)

    @returnlist
    def visit_Return(self, node):
        return self.visit(node.value)
