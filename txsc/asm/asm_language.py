import ast

from txsc.transformer import SourceVisitor, TargetVisitor
import txsc.linear_nodes as types
from txsc.language import Language

from txsc.asm import ASMParser

def get_lang():
    return ASMLanguage()

def format_hex(s):
    """Format a hex string.

    Ensure the string begins with '0x' and has an even
    number of characters.
    """
    # Make sure s is hex.
    try:
        _ = int(s, 16)
    except ValueError:
        return
    if s.startswith('0x'):
        s = s[2:]
    if len(s) % 2 == 1:
        s = '0' + s
    return '0x' + s

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
        if isinstance(value, int):
            push = self.int_to_bytearray(value)
            self.add_instruction(types.Push(data=push))
        else:
            try:
                smallint = int(value)
                opcode = self.get_small_int_class(smallint)
            except ValueError:
                opcode = self.get_opcode_class('OP_%s' % value)
            self.add_instruction(opcode)

class ASMTargetVisitor(TargetVisitor):
    """Transforms the linear representation into ASM."""
    def __init__(self, *args, **kwargs):
        super(ASMTargetVisitor, self).__init__(*args, **kwargs)
        self.values = []

    def process_instruction(self, instruction):
        result = self.visit(instruction)
        if isinstance(result, list):
            self.values.extend(result)
        else:
            self.values.append(result)

    def output(self):
        return ' '.join(self.values)

    def visit_Push(self, node):
        length = len(node.data)
        asm = []
        asm.append(format_hex(hex(length)))
        asm.append(format_hex(node.data.encode('hex')))
        return asm

    def generic_visit_OpCode(self, node):
        return node.name[3:]

    def generic_visit_SmallIntOpCode(self, node):
        return node.name[3:]


class ASMLanguage(Language):
    """ASM script language."""
    name = 'asm'
    source_visitor = ASMSourceVisitor
    target_visitor = ASMTargetVisitor
