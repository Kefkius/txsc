#!/usr/bin/env python
"""Displays the peephole optimizations performed by txsc."""

import argparse
from collections import namedtuple
import inspect
import json

from txsc.ir import linear_optimizer

Peephole = namedtuple('Peephole', ('before', 'after', 'function_name'))

def parse_comment(line):
    """Parse line into a (before, after) pair."""
    splitter = ' -> '

    if '#' not in line or splitter not in line:
        return
    line = line[line.index('#') + 1:].strip()
    idx = line.index(splitter)

    before = line[:idx]
    after = line[idx + len(splitter):]

    return (before, after)

def parse_source_lines(sourcelines):
    """Parse (before, after) pairs from comments in sourcelines."""
    optimizations = []
    for line in sourcelines:
        result = parse_comment(line)
        if not result:
            continue
        optimizations.append(result)

    return optimizations

def get_peephole_optimizations():
    """Parse the peephole optimizers and return their effects.

    Returns:
        A list of Peephole instances.

    """
    peepholes = []
    for func in linear_optimizer.peephole_optimizers:
        sourcelines, _ = inspect.getsourcelines(func)
        results = parse_source_lines(sourcelines)
        for before, after in results:
            peepholes.append(Peephole(before, after, func.__name__))

    return peepholes


def generate_json(peepholes, verbose=False):
    """Generate JSON-formatted results."""
    objects = []
    d = {'optimizations': objects}
    for i in peepholes:
        obj_dict = {'before': i.before, 'after': i.after}
        if verbose:
            obj_dict['function'] = i.function_name
        objects.append(obj_dict)
    return json.dumps(d, indent=4)

def generate_markdown(peepholes, verbose=False):
    """Generate markdown-formatted results."""
    header =  '| Before | After |'
    divider = '| ------ | ----- |'
    if verbose:
        header +=  ' Function |'
        divider += ' -------- |'

    s = [header, divider]

    for i in peepholes:
        line = '| %s | %s |' % (i.before, i.after)
        if verbose:
            line += ' %s |' % i.function_name
        s.append(line)
    return '\n'.join(s)

def generate_plain(peepholes, verbose=False):
    """Generate plain text results."""
    longest_before = len(peepholes[0].before)
    longest_after = len(peepholes[0].after)
    # Iterate to find the longest strings.
    for i in peepholes:
        if len(i.before) > longest_before:
            longest_before = len(i.before)
        if len(i.after) > longest_after:
            longest_after = len(i.after)

    format_str = '{:%d} -> {:%d}' % (longest_before, longest_after)
    if verbose:
        format_str += ' ({})'

    s = []
    for i in peepholes:
        format_args = [i.before, i.after]
        if verbose:
            format_args.append(i.function_name)
        line = format_str.format(*format_args)
        s.append(line)
    s.append('\nTotal: %d' % len(s))
    return '\n'.join(s)

def main():
    parser = argparse.ArgumentParser(description='Show the peephole optimizations that txsc performs.')

    output_group = parser.add_argument_group('output options')
    output_group.add_argument('-j', '--json', action='store_true', help='Generate results in JSON format.')
    output_group.add_argument('-m', '--markdown', action='store_true', help='Generate results in markdown format.')

    output_group.add_argument('-v', '--verbose', action='store_true', help='Show the function that each optimization is performed in.')

    args = parser.parse_args()

    peepholes = get_peephole_optimizations()
    # Check for duplicates.
    seen_befores = {}
    for i in peepholes:
        if i.before in seen_befores.keys():
            print('WARNING: Duplicate optimizations of %s (%s in %s and %s in %s)' % (i.before,
                    seen_befores[i.before].after, seen_befores[i.before].function_name,
                    i.after, i.function_name))
        else:
            seen_befores[i.before] = i

    output = ''
    if args.json:
        output = generate_json(peepholes, args.verbose)
    elif args.markdown:
        output = generate_markdown(peepholes, args.verbose)
    else:
        output = generate_plain(peepholes, args.verbose)

    print(output)

if __name__ == '__main__':
    main()
