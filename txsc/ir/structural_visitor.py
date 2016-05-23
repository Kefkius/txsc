from functools import wraps
import logging

from txsc.transformer import SourceVisitor
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

class StructuralVisitor(SourceVisitor):
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
    def visit_Assignment(self, node):
        if not self.symbol_table:
            raise Exception('Cannot assign value: No symbol table was supplied.')
        type_ = node.type_
        value = node.value
        # '_stack' is an invalid variable name that signifies stack assumptions.
        if node.name == '_stack':
            self.symbol_table.add_stack_assumptions(value)
        else:
            # Symbol value.
            if type_ == self.symbol_table.Symbol:
                other = self.symbol_table.lookup(value.name)
                type_ = other.type_
                value = other.value
            self.symbol_table.add_symbol(node.name, value, type_, node.mutable)
        return None

    @returnlist
    def visit_Symbol(self, node):
        if not self.symbol_table:
            raise Exception('Cannot process symbol: No symbol table was supplied.')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise Exception('Symbol "%s" was not declared.' % node.name)

        value = symbol.value
        type_ = symbol.type_
        # Add an assumption for the stack item.
        if type_ == 'stack_item':
            # Fail if there are assumptions after a conditional and the conditional branches do not result in the
            # same number of stack items.
            if self.after_uneven_conditional:
                raise Exception("Conditional branches must result in the same number of stack values, or assumptions afterward are not supported.")
            return types.Assumption(symbol.name, value)
        # Push the bytes of the byte array.
        elif type_ in ['byte_array', 'integer']:
            return self.visit(value)
        # If the type is an expression, then StructuralOptimizer could not simplify it.
        # Evaluate the expression as if it were encountered in the structural IR.
        elif type_ == 'expression':
            return self.visit(value)

    @returnlist
    def visit_If(self, node):
        test = self.visit(node.test)
        truebranch = self.visit(node.truebranch)
        falsebranch = []
        ops = test + [types.If()] + truebranch
        if node.falsebranch:
            falsebranch = self.visit(node.falsebranch)
            ops.extend([types.Else()] + falsebranch)
        ops.append(types.EndIf())

        if sum([i.delta for i in truebranch]) != sum([i.delta for i in falsebranch]):
            self.after_uneven_conditional = True
        return ops

    @returnlist
    def visit_Push(self, node):
        smallint = types.small_int_opcode(int(node))
        if smallint:
            return smallint()
        else:
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
                        raise ValueError(msg)
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
        if not self.symbol_table:
            raise Exception('Cannot process function call: No symbol table was supplied.')
        symbol = self.symbol_table.lookup(node.name)
        if not symbol:
            raise Exception('No function "%s" exists.' % node.name)
        elif symbol.type_ != self.symbol_table.Func:
            raise Exception('Cannot call "%s" of type %s' % (node.name, symbol.type_))

        func = symbol.value
        self.symbol_table.begin_scope()
        # Bind arguments to formal parameters.
        for param, arg in zip(func.args, node.args):
            # TODO use a specific symbol type instead of expression.
            self.symbol_table.add_symbol(name=param.id, value=arg, type_ = self.symbol_table.Expr)

        return_value = map(self.visit, func.body)
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
