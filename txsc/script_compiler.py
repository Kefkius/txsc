from collections import OrderedDict
import ast
import sys
from pkg_resources import iter_entry_points

from txsc.txscript import TxScriptLanguage
from txsc.asm import ASMLanguage
from txsc.btcscript import BtcScriptLanguage
from txsc.symbols import SymbolTable
from txsc.ir.instructions import LINEAR, STRUCTURAL
from txsc.ir.structural_visitor import StructuralVisitor
from txsc.ir.structural_optimizer import StructuralOptimizer
from txsc.ir.linear_optimizer import LinearOptimizer

# Load known languages in case we're running locally.
languages = [ASMLanguage, BtcScriptLanguage, TxScriptLanguage]
for entry_point in iter_entry_points(group='txsc.language'):
    lang_maker = entry_point.load()
    lang = lang_maker()
    if lang.name not in [i.name for i in languages]:
        languages.append(lang)

class DirectiveError(Exception):
    """Exception raised when a directive-related error is encountered."""
    def __init__(self, msg):
        super(DirectiveError, self).__init__('Directive error: %s' % msg)

class OptimizationLevel(object):
    """Level of optimization."""
    max_optimization = 3
    def __init__(self, value):
        self.set_value(value)

    def set_value(self, value):
        self.value = value
        # Whether to optimize the linear IR.
        self.optimize_linear = value > 0
        # Whether to optimize the structural IR.
        self.optimize_structural = value > 1
        # Whether to evaluate constant expressions in the structural IR.
        self.evaluate_structural = value > 2

class Verbosity(object):
    """Options that depend on verbosity."""
    max_verbosity = 3
    def __init__(self, value):
        self.set_value(value)

    def set_value(self, value):
        self.value = value
        self.quiet = value == 0     # Only output the compiled source.
        self.show_linear_ir = value > 0 # Show the linear intermediate representation.
        self.show_structural_ir = value > 1 # Show the structural intermediate representation.
        self.echo_input = value > 2 # Echo the source that was input.

class ScriptCompiler(object):
    """Script compiler."""
    def __init__(self):
        self.outputs = OrderedDict()
        self.symbol_table = None
        self.setup_languages()

    def setup_languages(self):
        self.langs = list(languages)
        self.input_languages = {i.name: i for i in filter(lambda cls: cls.has_source_visitor(), self.langs)}
        self.output_languages = {i.name: i for i in filter(lambda cls: cls.has_target_visitor(), self.langs)}

    def setup_options(self, options):
        self.options = options
        self.optimization = OptimizationLevel(getattr(self.options, 'optimization', OptimizationLevel.max_optimization))
        self.verbosity = Verbosity(self.options.verbosity)

        # Compilation source and target.
        self.source_lang = self.input_languages[self.options.source_lang]
        self.target_lang = self.output_languages[self.options.target_lang]

        self.output_file = self.options.output_file

    def process_directives(self, source_lines):
        """Parse any directives in source_lines."""
        # Extract directive lines from source_lines.
        directives = {}
        directive_lines = filter(lambda line: line.startswith('@'), source_lines)
        for i in directive_lines:
            source_lines.remove(i)
            try:
                key, value = i[1:].split(' ')
            except ValueError:
                raise DirectiveError('Invalid directive format.')
            else:
                directives[key] = value.replace('\n', '')

        # Target language.
        target = directives.get('target')
        if target:
            if target not in self.output_languages.keys():
                raise DirectiveError('Invalid choice for target: "%s"' % target)
            else:
                self.target_lang = self.output_languages[target]

        # Verbosity level.
        verbosity = directives.get('verbosity')
        if verbosity is not None:
            try:
                verbosity = int(verbosity) if verbosity != 'max' else Verbosity.max_verbosity
            except Exception:
                raise DirectiveError('Invalid verbosity level: "%s"' % verbosity)
            else:
                self.verbosity.set_value(verbosity)


    def compile(self, source_lines):
        self.outputs.clear()
        self.process_directives(source_lines)

        if self.verbosity.echo_input:
            self.outputs['Input'] = source_lines

        self.symbol_table = SymbolTable()
        # Add symbol_table to arguments if the source lang supports it.
        args = [source_lines]
        if self.source_lang.supports_symbol_table:
            args.append(self.symbol_table)

        try:
            instructions = self.source_lang().process_source(*args)
        except SyntaxError as e:
            print('Error encountered during compilation of source:')
            print(e)
            sys.exit(1)

        self.process_ir(instructions)

    def process_ir(self, instructions):
        """Process intermediate representation."""
        # Convert structural to linear representation.
        if instructions.ir_type == STRUCTURAL:
            if self.verbosity.show_structural_ir:
                self.outputs['Structural Intermediate Representation'] = instructions.dump()
            # Optimize structural IR.
            if self.optimization.optimize_structural:
                StructuralOptimizer().optimize(instructions, self.symbol_table, self.optimization.evaluate_structural)
                if self.verbosity.show_structural_ir:
                    self.outputs['Optimized Structural Representation'] = instructions.dump()
            instructions = StructuralVisitor().transform(instructions.script, self.symbol_table)

        if self.verbosity.show_linear_ir:
            self.outputs['Linear Intermediate Representation'] = str(instructions)

        # Perform linear IR optimizations. Perform peephole optimizations if specified.
        # TODO: If the target language supports symbols, do not inline.
        LinearOptimizer().optimize(instructions, peephole=self.optimization.optimize_linear, inline=True)
        if self.verbosity.show_linear_ir:
            self.outputs['Optimized Linear Representation'] = str(instructions)

        self.process_targets(instructions)

    def process_targets(self, instructions):
        """Process compilation targets."""
        self.outputs[self.target_lang.name] = self.target_lang().compile_instructions(instructions)

    def output(self):
        """Output results."""
        formats = OrderedDict(self.outputs)
        # Hide optimized representation if no optimizations were performed.
        for normal, optimized in [
            ('Linear Intermediate Representation', 'Optimized Linear Representation'),
            ('Structural Intermediate Representation', 'Optimized Structural Representation'),
        ]:
            outputs = map(formats.get, [normal, optimized])
            if all(i is not None for i in outputs) and outputs[0] == outputs[1]:
                del formats[optimized]

        s = ['%s:\n  %s\n' % (k, v) for k, v in formats.items()]
        s = '\n'.join(s)
        if s.endswith('\n'):
            s = s[:-1]
        if self.verbosity.quiet:
            s = self.outputs[self.target_lang.name]

        if self.output_file:
            with open(self.output_file, 'w') as f:
                f.write(s)
            return 'Compiled %s to %s in %s' % (self.source_lang.name, self.target_lang.name, self.output_file)
        else:
            return s
