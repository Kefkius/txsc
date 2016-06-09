#!/usr/bin/env python
import argparse
import os
import sys
import logging

# Check is txsc is being run locally.
is_local = False
try:
    import txsc
except ImportError:
    is_local = True
# If running locally, add txsc to path.
if is_local:
    path = os.getcwd()
    # Remove last directory if running from txsc/txsc.
    if os.path.dirname(path).endswith('txsc'):
        path = path[:-4]
    while path.endswith(('/', '\\')):
        path = path[:-1]
    sys.path.insert(0, path)

from txsc.script_compiler import DirectiveError, ScriptCompiler, OptimizationLevel, Verbosity
from txsc import config

# Will not reload the entry points if they've already been loaded.
config.load_entry_points()


# http://stackoverflow.com/questions/6076690/verbose-level-with-argparse-and-multiple-v-options
class VAction(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if values==None:
            values='1'
        try:
            values=int(values)
        except ValueError:
            values=values.count('v')+1
        setattr(args, self.dest, values)

class OAction(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        if values==None:
            values='1'
        try:
            values=int(values)
        except ValueError:
            values=values.count('O')+1
        setattr(args, self.dest, values)

class LogAction(argparse.Action):
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = ['debug', 'info', 'warning', 'error', 'none']
        super(LogAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, args, values, option_string=None):
        if values==None:
            values='warning'
        elif values in ['off', 'none']:
            values='fatal'
        elif values=='warn':
            values='warning'

        if not isinstance(values, str):
            values='warning'
        values = values.upper()
        setattr(args, self.dest, values)

source_choices = []
target_choices = []
opcode_set_choices = []

def create_arg_parser():
    argparser = argparse.ArgumentParser(description='Transaction script compiler.')
    argparser.add_argument('source', metavar='SOURCE', nargs='?', type=str, help='Source to compile.')
    argparser.add_argument('--list-langs', dest='list_langs', action='store_true', default=False, help='List available languages and exit.')
    argparser.add_argument('--list-opcode-sets', dest='list_opcode_sets', action='store_true', default=False, help='List available opcode sets and exit.')
    argparser.add_argument('-o', '--output', dest='output_file', metavar='OUTPUT_FILE', type=str, help='Output to a file.')
    argparser.add_argument('-O', '--optimize', nargs='?', action=OAction, dest='optimization', metavar='OPTIMIZATION_LEVEL', default=2, help='Optimization level (Max: %d).' % OptimizationLevel.max_optimization)

    argparser.add_argument('-s', '--source', metavar='SOURCE_LANGUAGE', dest='source_lang', choices=source_choices, default='txscript', help='Source language (Choices: %(choices)s).')
    argparser.add_argument('-t', '--target', metavar='TARGET_LANGUAGE', dest='target_lang', choices=target_choices, default='btc', help='Target language (Choices: %(choices)s).')
    argparser.add_argument('--opcode-set', metavar='OPCODE_SET', dest='opcode_set', choices=opcode_set_choices,
                           default='default', help='Opcode set (Choices: %(choices)s).')

    argparser.add_argument('--log', nargs='?', action=LogAction, dest='log_level', default='WARNING', help='Minimum logging level (Default: %(default)s).')
    argparser.add_argument('-v', '--verbose', nargs='?', action=VAction, dest='verbosity', default=0, help='Verbosity level (Max: %d).' % Verbosity.max_verbosity)

    group = argparser.add_argument_group('compilation flags', 'These optional flags place restrictions on script contents.')
    group.add_argument('--no-implicit-pushes', dest='no_implicit_pushes', action='store_true', default=False, help='Fail if values are implicitly pushed to the stack.')
    group.add_argument('--strict-num', dest='strict_num', action='store_true', default=False, help='Fail if values larger than 4 bytes are treated as integers.')


    return argparser

def main():
    global source_choices, target_choices, opcode_set_choices
    logger = logging.getLogger('txsc')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(levelname)s [%(name)s] %(message)s'))
    logger.addHandler(ch)


    compiler = ScriptCompiler()
    source_choices = sorted(compiler.input_languages.keys())
    target_choices = sorted(compiler.output_languages.keys())
    opcode_set_choices = sorted(config.get_opcode_sets().keys())

    argparser = create_arg_parser()
    args = argparser.parse_args()

    def list_languages():
        """List available languages."""
        langs = {lang.name: lang.__doc__ for lang in compiler.langs}
        s = []
        longest = max([len(name) for name in langs.keys()])
        fmt = '{:<%d}: {}' % (longest + 1)
        for k, v in sorted(langs.items(), key = lambda i: i[0]):
            s.append(fmt.format(k, v))
        s = '\n'.join(s)
        print(s)

    def list_opcode_sets():
        """List available opcode sets."""
        s = sorted(config.get_opcode_sets().keys())
        s = '\n'.join(s)
        print(s)


    # Determine whether source is needed.
    if args.list_langs:
        list_languages()
        argparser.exit(0)
    elif args.list_opcode_sets:
        list_opcode_sets()
        argparser.exit(0)
    elif args.source is None:
        argparser.print_usage()
        argparser.exit(1)

    s = args.source
    src = [s]
    if os.path.exists(s):
        with open(s, 'r') as f:
            src = f.readlines()
        # Automatically detect source language from file extension.
        names = s.split('.')
        if len(names) > 1 and names[-1] in source_choices:
            args.source_lang = names[-1]

    compiler.setup_options(args)
    try:
        compiler.compile(src)
    except DirectiveError as e:
        print(str(e))
        sys.exit(1)
    print(compiler.output())

if __name__ == '__main__':
    main()
