from collections import OrderedDict
import argparse
import ast
import json
import os
import sys
from pkg_resources import iter_entry_points
import logging

from txsc.symbols import SymbolTable
from txsc.ir.instructions import LINEAR, STRUCTURAL
from txsc.ir.linear_visitor import LIROptions
from txsc.ir.structural_visitor import SIROptions, StructuralVisitor, IRError
from txsc.ir.structural_optimizer import StructuralOptimizer
from txsc.ir import linear_optimizer
from txsc.txscript import ParsingError
from txsc import config

# Will not reload the entry points if they've already been loaded.
config.load_entry_points()

def set_log_level(level):
    """Set the minimum logging level."""
    level = level.upper()
    log_level = getattr(logging, level, logging.WARNING)
    logging.getLogger('txsc').setLevel(log_level)


class DirectiveError(Exception):
    """Exception raised when a directive-related error is encountered."""
    def __init__(self, msg):
        super(DirectiveError, self).__init__('Directive error: %s' % msg)

class OptimizationLevel(object):
    """Level of optimization."""
    max_optimization = 2
    def __init__(self, value):
        self.set_value(value)

    def set_value(self, value):
        self.value = value
        # Whether to optimize the linear IR.
        self.optimize_linear = value > 0
        # Whether to evaluate constant expressions in the structural IR.
        self.evaluate_structural = value > 1

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

class CompilationOptions(object):
    """Model of script compilation options."""
    def __init__(self, options):
        if isinstance(options, argparse.Namespace):
            options = options.__dict__
        self.supplied_options = options.keys()

        defaults = {
            'optimization': OptimizationLevel.max_optimization,
            'log_level': 'WARNING',
            'verbosity': 0,
            'source_lang': 'txscript',
            'target_lang': 'btc',
            'opcode_set': 'default',
            'config_file': '',
            'output_file': '',
            'no_implicit_pushes': False,
            'strict_num': False,
        }
        for k, v in defaults.items():
            if k not in options.keys():
                options[k] = v

        for k, v in options.items():
            setattr(self, k, v)

class ScriptCompiler(object):
    """Script compiler."""
    @staticmethod
    def load_file(path):
        try:
            with open(path, 'r') as f:
                config_options = json.loads(f.read())
                if isinstance(config_options, dict):
                    return config_options
        except Exception:
            pass
        return None


    @staticmethod
    def load_config_file():
        """Find a configuration file (if it exists) and load its options."""
        filename = 'txsc.conf'
        paths = [os.getcwd()]
        if os.environ.get('HOME'):
            paths.append(os.path.join(os.environ['HOME'], '.config', 'txsc'))

        for directory in paths:
            path = os.path.join(directory, filename)
            config_options = ScriptCompiler.load_file(path)
            if config_options is not None:
                return config_options

        return {}

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.outputs = OrderedDict()
        self.symbol_table = None
        self.source_lines = []
        self.setup_languages()
        # If true, sys.exit() will not be called when failing.
        self.testing_mode = False

    def setup_languages(self):
        self.langs = config.get_languages()
        self.input_languages = {i.name: i for i in filter(lambda cls: cls.has_source_visitor(), self.langs)}
        self.output_languages = {i.name: i for i in filter(lambda cls: cls.has_target_visitor(), self.langs)}

    def setup_options(self, options):
        if not isinstance(options, CompilationOptions):
            options = CompilationOptions(options)
        self.options = options

        # Load options from config file (if one exists).
        if self.options.config_file:
            config_options = self.load_file(self.options.config_file)
        else:
            config_options = self.load_config_file()
        if config_options:
            for k, v in config_options.items():
                if k not in self.options.supplied_options:
                    setattr(self.options, k, v)


        self.optimization = OptimizationLevel(self.options.optimization)
        self.verbosity = Verbosity(self.options.verbosity)
        set_log_level(self.options.log_level)

        # Compilation source and target.
        self.source_lang = self.input_languages[self.options.source_lang]
        self.target_lang = self.output_languages[self.options.target_lang]

        # LIR options.
        self.lir_options = LIROptions(inline_assumptions=True,
                        peephole_optimizations=self.optimization.optimize_linear)

        # SIR options.
        self.sir_options = SIROptions(evaluate_expressions=self.optimization.evaluate_structural,
                        implicit_pushes=not self.options.no_implicit_pushes,
                        strict_num=self.options.strict_num)

        # Opcode set.
        config.set_opcode_set(self.options.opcode_set)
        # Linear optimizer.
        config.set_linear_optimizer(self.options.opcode_set)

        self.output_file = self.options.output_file

    def process_directives(self, source_lines):
        """Parse any directives in source_lines."""
        # Extract directive lines from source_lines.
        directives = {}
        directive_lines = filter(lambda line: line.startswith('@'), source_lines)
        for i in directive_lines:
            # Replace directive with a newline.
            idx = source_lines.index(i)
            source_lines.remove(i)
            source_lines.insert(idx, '\n')
            try:
                key, value = i[1:].split(' ')
            except ValueError:
                raise DirectiveError('Invalid directive format.')
            else:
                directives[key] = value.replace('\n', '')

        # Opcode set.
        opcode_set = directives.get('opcode-set')
        if opcode_set:
            if opcode_set not in config.get_opcode_sets().keys():
                valid_opcode_sets = ''.join(['\n- %s' % name for name in config.get_opcode_sets().keys()])
                raise DirectiveError('Invalid choice for opcode set: "%s"\nValid choices are:%s' % (opcode_set, valid_opcode_sets))
            else:
                config.set_opcode_set(opcode_set)
                self.logger.debug('Compiler directive: Opcode set = %s' % opcode_set)

        # Target language.
        target = directives.get('target')
        if target:
            if target not in self.output_languages.keys():
                valid_targets = ''.join(['\n- %s' % name for name in self.output_languages.keys()])
                raise DirectiveError('Invalid choice for target: "%s"\nValid choices are:%s' % (target, valid_targets))
            else:
                self.target_lang = self.output_languages[target]
                self.logger.debug('Compiler directive: Target lang = %s' % target)

        # Verbosity level.
        verbosity = directives.get('verbosity')
        if verbosity is not None:
            try:
                verbosity = int(verbosity) if verbosity != 'max' else Verbosity.max_verbosity
            except Exception:
                raise DirectiveError('Invalid verbosity level: "%s"' % verbosity)
            else:
                self.verbosity.set_value(verbosity)
                self.logger.debug('Compiler directive: Verbosity = %s' % verbosity)


    def compile(self, source_lines):
        self.outputs.clear()
        self.process_directives(source_lines)

        if self.verbosity.echo_input:
            self.outputs['Input'] = source_lines
        self.source_lines = list(source_lines)

        self.symbol_table = SymbolTable()
        # Add symbol_table to arguments if the source lang supports it.
        args = [source_lines]
        if self.source_lang.supports_symbol_table:
            args.append(self.symbol_table)

        try:
            instructions = self.source_lang().process_source(*args)
        except ParsingError as e:
            if self.testing_mode:
                raise e
            print('%s encountered during compilation of source:' % e.__class__.__name__)
            print(e)
            sys.exit(1)

        self.process_ir(instructions)

    def process_ir(self, instructions):
        """Process intermediate representation."""
        # Convert structural to linear representation.
        if instructions.ir_type == STRUCTURAL:
            ast.fix_missing_locations(instructions.script)
            if self.verbosity.show_structural_ir:
                self.outputs['Structural Intermediate Representation'] = instructions.dump()
            try:
                # Optimize structural IR.
                StructuralOptimizer(self.sir_options).optimize(instructions, self.symbol_table)
                if self.verbosity.show_structural_ir:
                    self.outputs['Optimized Structural Representation'] = instructions.dump()

                instructions = StructuralVisitor(self.sir_options).transform(instructions, self.symbol_table)
            except IRError as e:
                if self.testing_mode:
                    raise e
                lineno = e.args[1]
                msg = 'On line %d:\n\t' % lineno
                msg += self.source_lines[lineno - 1]
                if e.args[0]:
                    msg += '\n' + e.args[0]
                print('%s encountered in intermediate representation:' % e.__class__.__name__)
                print(msg)
                sys.exit(1)

        if self.verbosity.show_linear_ir:
            self.outputs['Linear Intermediate Representation'] = str(instructions)

        # Perform linear IR optimizations. Perform peephole optimizations if specified.
        # TODO: If the target language supports symbols, do not inline.
        optimizer = linear_optimizer.get_linear_optimizer_cls()
        optimizer(self.symbol_table, self.lir_options).optimize(instructions)
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
                self.logger.info('Omitting redundant output "%s"' % optimized)
                del formats[optimized]

        s = ['%s:\n  %s\n' % (k, v) for k, v in formats.items()]
        s = '\n'.join(s)
        if s.endswith('\n'):
            s = s[:-1]
        if self.verbosity.quiet:
            s = self.outputs[self.target_lang.name]
        else:
            s = '------ Results ------\n' + s

        if self.output_file:
            with open(self.output_file, 'w') as f:
                f.write(s)
            return 'Compiled %s to %s in %s' % (self.source_lang.name, self.target_lang.name, self.output_file)
        else:
            return s
