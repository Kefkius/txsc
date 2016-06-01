from functools import wraps
import logging

from txsc.symbols import SymbolType, ImmutableError, MultipleDeclarationsError, UndeclaredError
from txsc.transformer import BaseTransformer
from txsc.ir import formats, structural_nodes
from txsc.ir.instructions import LInstructions, SInstructions
import txsc.ir.linear_nodes as types

logger = logging.getLogger(__name__)

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

class IRStrictNumError(IRError):
    """Exception raised when using a non-number value in an arithmetic operation."""
    pass

class IRTypeError(IRError):
    """Exception raised when using incompatible or incorrect types."""
    pass

class BaseStructuralVisitor(BaseTransformer):
    """Base class for structural visitors."""
    symbol_table = None

    def require_symbol_table(self, purpose=None):
        """Raise an exception if no symbol table is present."""
        if not purpose:
            purpose = 'process'
        if not self.symbol_table:
            raise Exception('Cannot %s: No symbol table was supplied to %s.' % (purpose, self.__class__.__name__))

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
        return structural_nodes.Assignment(node.name, value, type_)

    def add_Assignment(self, node):
        """Add an assignment to the symbol table."""
        self.require_symbol_table('assign value')

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

class StructuralVisitor(BaseStructuralVisitor):
    """Tranforms a structural representation into a linear one."""
    def transform(self, node, symbol_table=None, strict_num=False):
        # Whether we've finished visiting a conditional that results in a different
        # number of stack items depending on whether or not it is true.
        self.after_uneven_conditional = False
        self.symbol_table = symbol_table
        self.strict_num = strict_num
        self.script = node
        self.instructions = LInstructions(self.visit(node.script))
        return self.instructions

    def visit(self, node):
        try:
            return super(StructuralVisitor, self).visit(node)
        except IRError as e:
            raise e.__class__(e.args[0], node.lineno)

    @returnlist
    def visit_list(self, node):
        return self.visit(structural_nodes.Push(''.join(node)))

    @returnlist
    def visit_Script(self, node):
        return_value = []
        for stmt in node.statements:
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
    def visit_Int(self, node):
        smallint = types.small_int_opcode(int(node))
        if smallint:
            return smallint()
        else:
            return types.Push(formats.int_to_bytearray(node.value))

    @returnlist
    def visit_Push(self, node):
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
        return_value = self.visit(node.operand)
        op = types.opcode_by_name(node.name)()
        return return_value + [op]

    @returnlist
    def visit_BinOpCode(self, node):
        # Check for values longer than 4 bytes.
        if SInstructions.is_arithmetic_op(node):
            operands = [node.left, node.right]
            if all(isinstance(i, structural_nodes.Push) for i in operands):
                valid = [formats.is_strict_num(int(i)) for i in operands]
                if False in valid:
                    msg = 'Input value is longer than 4 bytes: 0x%x' % operands[valid.index(False)]
                    if self.strict_num:
                        logger.error(msg)
                        raise IRStrictNumError(msg)
                    else:
                        logger.warning(msg)

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
        self.require_symbol_table('process function call')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise IRError('No function "%s" exists.' % node.name)
        elif symbol.type_ != SymbolType.Func:
            raise IRTypeError('Cannot call "%s" of type %s' % (node.name, symbol.type_))

        func = symbol.value
        self.symbol_table.begin_scope()
        # Bind arguments to formal parameters.
        for param, arg in zip(func.args, node.args):
            # TODO use a specific symbol type instead of expression.
            self.symbol_table.add_symbol(name=param.id, value=arg, type_ = SymbolType.Expr, declaration=True)

        return_value = self.map_visit(func.body)
        # Visiting returns a list.
        if len(return_value):
            values = list(return_value)
            return_value = []
            for v in values:
                return_value.extend(v)
        self.symbol_table.end_scope()

        return return_value

    @returnlist
    def visit_Function(self, node):
        return None
