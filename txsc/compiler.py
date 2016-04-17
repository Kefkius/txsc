#!/usr/bin/env python
import argparse
import os
import sys

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

from txsc.script_compiler import ScriptCompiler, Verbosity


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

def main():
    compiler = ScriptCompiler()
    source_choices = sorted(compiler.input_languages.keys())
    target_choices = sorted(compiler.output_languages.keys())

    argparser = argparse.ArgumentParser(description='Transaction script compiler.')
    argparser.add_argument('source', metavar='SOURCE', nargs='?', type=str, help='Source to compile.')
    argparser.add_argument('-l', '--list', dest='list_langs', action='store_true', default=False, help='List available languages and exit.')
    argparser.add_argument('-o', '--output', dest='output_file', metavar='OUTPUT_FILE', type=str, help='Output to a file.')

    argparser.add_argument('-s', '--source', metavar='SOURCE_LANGUAGE', dest='source_lang', choices=source_choices, default='txscript', help='Source language.')
    argparser.add_argument('-t', '--target', metavar='TARGET_LANGUAGE', dest='target_lang', choices=target_choices, default='btc', help='Target language.')

    argparser.add_argument('--no-optimize', dest='no_optimize', action='store_true', default=False, help='Do not perform optimizations on script.')
    argparser.add_argument('-v', '--verbose', nargs='?', action=VAction, dest='verbosity', default=0, help='Verbosity level (Max: %d).' % Verbosity.max_verbosity)

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


    # Determine whether source is needed.
    if args.list_langs:
        list_languages()
        argparser.exit(0)
    elif args.source is None:
        argparser.print_usage()
        argparser.exit(1)

    s = args.source
    src = [s]
    try:
        if os.path.exists(s):
            with open(s, 'r') as f:
                src = f.readlines()
                src = map(lambda line: line.replace('\n', ''), src)
    except Exception:
        pass

    compiler.setup_options(args)
    compiler.compile(src)

if __name__ == '__main__':
    main()
