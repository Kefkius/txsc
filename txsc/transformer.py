import ast

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp

import txsc.ir.linear_nodes as types
from txsc.ir.instructions import LINEAR, get_instructions_class

class BaseTransformer(ast.NodeTransformer):
    """Base class for transformers."""
    debug = False
    def debug_print(self, s):
        """Print something if self.debug is True."""
        if self.debug:
            print('[%s] > %s' % (self.__class__.__name__, s))

    def generic_visit(self, node):
        self.debug_print('generic_visit %s' % node.__class__.__name__)
        super(BaseTransformer, self).generic_visit(node)

    def format_dump(self, node, annotate_fields=True, include_attributes=False):
        if isinstance(node, ast.AST):
            fields = [(a, self.format_dump(b, annotate_fields, include_attributes)) for a, b in ast.iter_fields(node)]
            rv = '%s(%s' % (node.__class__.__name__, ', '.join(
                ('%s=%s' % field for field in fields)
                if annotate_fields else
                (b for a, b in fields)
            ))
            if include_attributes and node._attributes:
                rv += fields and ', ' or ' '
                rv += ', '.join('%s=%s' % (a, _format(getattr(node, a)))
                                for a in node._attributes)
            return rv + ')'
        elif isinstance(node, list):
            return '[%s]' % ', '.join(self.format_dump(x, annotate_fields, include_attributes) for x in node)
        return repr(node)

    def dump(self, node, annotate_fields=False, include_attributes=False):
        if not isinstance(node, ast.AST):
            raise TypeError('expected AST, got %r' % node.__class__.__name__)
        return self.format_dump(node, annotate_fields, include_attributes)

class SourceVisitor(BaseTransformer):
    """Visitor that operates on a source language."""
    # Type of instructions that this visitor generates.
    ir_type = LINEAR

    @staticmethod
    def int_to_bytearray(value):
        """Encode an integer as a byte array."""
        try:
            value = int(CScriptOp.encode_op_n(value))
        except ValueError:
            pass
        return _bignum.bn2vch(value)

    def __init__(self, *args, **kwargs):
        super(SourceVisitor, self).__init__(*args, **kwargs)
        self.instructions = get_instructions_class(self.ir_type)()

    def add_instruction(self, node):
        """Add a single instruction."""
        if self.ir_type != LINEAR:
            raise Exception('Visitor must generate linear IR instructions to use this method')
        self.instructions.append(node)

    def transform(self, source):
        """Visit source and generate instructions."""
        return self.instructions

    def get_opcode_class(self, name):
        """Get the linear node opcode type for name."""
        if self.ir_type != LINEAR:
            raise Exception('Visitor must generate linear IR instructions to use this method')
        return types.opcode_classes[name]()

    def get_small_int_class(self, value):
        """Get the linear node small int opcode type for value."""
        if self.ir_type != LINEAR:
            raise Exception('Visitor must generate linear IR instructions to use this method')
        return self.get_opcode_class('OP_%d'%value)

class TargetVisitor(BaseTransformer):
    """Visitor that operates on the linear intermediate representation."""
    def process_instruction(self, instruction):
        """Process a single instruction."""
        pass

    def compile(self, instructions):
        """Visit instructions and generate target values."""
        map(self.process_instruction, instructions)
        return self.output()

    def output(self):
        """Return the compiled source."""
        pass

    def generic_visit_OpCode(self, node):
        """Called if no explicit visitor method exists for an OpCode."""
        return node

    def generic_visit_SmallIntOpCode(self, node):
        """Called if no explicit visitor method exists for a SmallIntOpCode."""
        return node

    def generic_visit(self, node):
        if isinstance(node, types.SmallIntOpCode):
            node = self.generic_visit_SmallIntOpCode(node)
        elif isinstance(node, types.OpCode):
            node = self.generic_visit_OpCode(node)
        else:
            node = super(TargetVisitor, self).generic_visit(node)
        return node
