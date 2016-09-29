import ast

import hexs

from txsc.transformer import SourceVisitor, TargetVisitor
from txsc.ir import formats
import txsc.ir.linear_nodes as types
from txsc.language import Language

from txsc.asm import ASMParser
from txsc.btcscript import BtcScriptTargetVisitor

def get_lang():
    return ASMLanguage()

def format_hex(s):
    """Format a hex string.

    Ensure the string begins with '0x' and has an even
    number of characters.
    """
    if not hexs.is_hex(s):
        return
    return '0x' + hexs.format_hex(s)

class ASMSourceVisitor(SourceVisitor):
    """Transforms ASM into the linear representation."""

    def transform(self, source):
        parser = ASMParser()
        if isinstance(source, list):
            source = '\n'.join(source)
        parsed = parser.parse_source(source)

        if parsed is None:
            print('\nFailed to parse.\n')
        assert isinstance(parsed, list)
        map(self.process_value, parsed)
        return self.instructions

    def process_value(self, value):
        # Encode integer.
        if isinstance(value, (int, long)):
            push = formats.int_to_bytearray(value)
            self.add_instruction(types.Push(data=push))
        else:
            try:
                opcode = types.small_int_opcode(int(value))()
            except (TypeError, ValueError):
                opcode = types.opcode_by_name('OP_%s' % value)()
            self.add_instruction(opcode)

class ASMTargetVisitor(BtcScriptTargetVisitor):
    """Transforms the linear representation into ASM."""
    def __init__(self, *args, **kwargs):
        self.omit_op_prefixes = True
        if kwargs.get('omit_op_prefixes') is not None:
            self.omit_op_prefixes = kwargs['omit_op_prefixes']
            del kwargs['omit_op_prefixes']
        super(ASMTargetVisitor, self).__init__(*args, **kwargs)
        self.values = []
        # If we're transforming an InnerScript, we use BtcScriptTargetVisitor
        # to get the actual values of opcodes.
        self.visiting_innerscript = False
        self.little_endian = False

    def process_instruction(self, instruction):
        result = self.visit(instruction)
        if result is None:
            return
        if isinstance(result, list):
            self.values.extend(result)
        else:
            self.values.append(result)

    def output(self):
        return ' '.join(self.values)

    def visit_Declaration(self, node):
        return None

    def visit_Assignment(self, node):
        return None

    def visit_Variable(self, node):
        return None

    def visit_InnerScript(self, node):
        """Use BtcScriptTargetVisitor to transform node."""
        self.visiting_innerscript = True
        value = super(ASMTargetVisitor, self).visit_InnerScript(node)
        self.visiting_innerscript = False
        return value

    def visit_Push(self, node):
        length = len(node.data)
        asm = []
        asm.append(format_hex(hex(length)))
        asm.append(format_hex(node.data.encode('hex')))
        return asm

    def generic_visit_OpCode(self, node):
        if self.visiting_innerscript:
            return super(ASMTargetVisitor, self).generic_visit_OpCode(node)
        return node.name[3:] if self.omit_op_prefixes else node.name

    def generic_visit_SmallIntOpCode(self, node):
        if self.visiting_innerscript:
            return super(ASMTargetVisitor, self).generic_visit_SmallIntOpCode(node)
        return node.name[3:] if self.omit_op_prefixes else node.name


class ASMLanguage(Language):
    """ASM script language."""
    name = 'asm'
    source_visitor = ASMSourceVisitor
    target_visitor = ASMTargetVisitor
