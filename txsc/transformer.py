import ast
import logging

import txsc.ir.linear_nodes as types
from txsc.ir.instructions import LINEAR, get_instructions_class

class BaseTransformer(ast.NodeTransformer):
    """Base class for transformers."""
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__module__)

    def _prepend_lineno(self, msg, lineno):
        """Prepend line number to msg."""
        if lineno is not None:
            msg = 'Line %d: %s' % (lineno, msg)
        return msg

    def debug(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.debug(msg)

    def info(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.info(msg)

    def warning(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.warning(msg)

    def error(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.error(msg)

    def critical(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.critical(msg)

    def fatal(self, msg, lineno=None):
        msg = self._prepend_lineno(msg, lineno)
        self.logger.fatal(msg)

    def map_visit(self, nodes):
        """Return the results of visiting each node in nodes.

        This is a convenience method equivalent to 'map(self.visit, nodes)'.
        """
        return map(self.visit, nodes)

    def generic_visit(self, node):
        return super(BaseTransformer, self).generic_visit(node)

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
