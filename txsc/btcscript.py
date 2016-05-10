"""Raw script language.

Uses python-bitcoinlib internally.
"""

from bitcoin.core import b2x, x, script

from txsc.transformer import SourceVisitor, TargetVisitor
import txsc.ir.linear_nodes as types
from txsc.language import Language

def get_lang():
    return BtcScriptLanguage()

class BtcScriptSourceVisitor(SourceVisitor):
    """Transforms raw scripts into the intermediate representation."""
    def transform(self, source):
        if isinstance(source, list):
            source = ''.join(source)
        if source.startswith('0x'):
            source = source[2:]

        src = script.CScript(x(source))
        iterator = iter(src)
        for value in iterator:
            op = None
            s = str(value)
            if s.startswith('OP_'):
                op = types.opcode_by_name(s)()
            elif isinstance(value, int):
                op = types.small_int_opcode(value)()
            else:
                op = types.Push(data=value)

            if op is not None:
                self.add_instruction(op)

        return self.instructions

class BtcScriptTargetVisitor(TargetVisitor):
    """Transforms the intermediate representation into raw scripts."""
    def __init__(self, *args, **kwargs):
        super(BtcScriptTargetVisitor, self).__init__(*args, **kwargs)
        self.hex_strs = []

    def process_instruction(self, instruction):
        result = self.visit(instruction)
        self.hex_strs.append(result)

    def output(self):
        return ''.join(self.hex_strs)

    def visit_InnerScript(self, node):
        s = []
        for op in node.ops:
            result = self.visit(op)
            if isinstance(result, list):
                result = ''.join(result).replace('0x','')
            s.append(result)
        s = ''.join(s)
        return self.visit(types.Push(data=x(s)))

    def visit_Push(self, node):
        value = script.CScriptOp.encode_op_pushdata(node.data)
        return b2x(value)

    def generic_visit_OpCode(self, node):
        value = int(script.OPCODES_BY_NAME[node.name])
        return hex(value)[2:]

    def generic_visit_SmallIntOpCode(self, node):
        return self.generic_visit_OpCode(node)

class BtcScriptLanguage(Language):
    """Raw Bitcoin script language."""
    name = 'btc'
    source_visitor = BtcScriptSourceVisitor
    target_visitor = BtcScriptTargetVisitor
