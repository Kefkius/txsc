import ast
from ply import yacc

from txsc.ir.instructions import STRUCTURAL, SInstructions
from txsc.language import Language
from txsc.transformer import SourceVisitor
from txsc.txscript import ScriptParser, ScriptTransformer, ParsingError, ScriptSyntaxError
from txsc.symbols import SymbolTable

def get_lang():
    return TxScriptLanguage

class TxScriptSourceVisitor(SourceVisitor):
    """Wrapper around txscript classes."""
    ir_type = STRUCTURAL
    def __init__(self, *args, **kwargs):
        super(TxScriptSourceVisitor, self).__init__(*args, **kwargs)
        # Set up yacc.
        self.parser = ScriptParser()

    def transform(self, source, symbol_table):
        if isinstance(source, list):
            source = ''.join(source)

        def raise_parsing_error(e, line_number, cls=ParsingError):
            """Raise an error with the line it occurs on."""
            msg = 'On line %d:\n\t' % line_number
            msg += source.split('\n')[line_number - 1]
            msg += '\n' + e.args[0]
            raise cls(msg)

        # Sanity check: Ensure that at least one statement exists.
        if ';' not in source:
            raise ParsingError('Source contains no statements.')
        try:
            node = self.parser.parse(source)
        except ScriptSyntaxError as e:
            raise_parsing_error(e, e.args[1].lineno)

        if not isinstance(node, ast.Module):
            node = ast.Module(body=node)
        ast.fix_missing_locations(node)

        # Convert AST to structural representation.
        try:
            node = ScriptTransformer(symbol_table).visit(node)
        except ParsingError as e:
            raise_parsing_error(e, e.args[1], cls=e.__class__)

        return SInstructions(node)


class TxScriptLanguage(Language):
    """Python-based TxScript language."""
    name = 'txscript'
    source_visitor = TxScriptSourceVisitor
    supports_symbol_table = True
