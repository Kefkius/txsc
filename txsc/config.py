"""txsc configuration.

Handles configuration values and entry points.

Entry points have the following requirements:

    - txsc.language: Must return an instance of a txsc.language.Language subclass.
    - txsc.opcodes: Must return a 2-tuple of the form (name, opcodes), where:
        - name (str): The name of the opcode set.
        - opcodes (dict): A dict of {opcode_name: opcode_class}.

        Opcode classes must be subclasses of txsc.ir.linear_nodes.OpCode. They
        may optionally have an attribute, "func", which is a txsc.txscript.script_transformer.OpFunc
        instance. If this attribute is present, the OpFunc name will be available as a built-in function.
"""

import os
from pkg_resources import iter_entry_points


# Default languages.
from txsc.language import Language
from txsc.txscript import TxScriptLanguage
from txsc.asm import ASMLanguage
from txsc.btcscript import BtcScriptLanguage

# Default opcodes.
from txsc.ir import linear_nodes

# Default builtin functions.
from txsc.txscript import script_transformer

# Whether entry points have been loaded.
_loaded = False
def has_loaded():
    """Return whether entry points have been loaded."""
    return _loaded


# Configurable collections.
languages = [ASMLanguage, BtcScriptLanguage, TxScriptLanguage]
opcode_sets = {'default': linear_nodes.get_opcodes()}


def load_languages():
    """Load languages from entry points."""
    global languages
    for entry_point in iter_entry_points(group='txsc.language'):
        lang_maker = entry_point.load()
        lang = lang_maker()
        # Must be a Language subclass instance.
        if not isinstance(lang, Language):
            continue
        # The language must not have a duplicate name.
        if lang.name in [i.name for i in languages]:
            continue
        languages.append(lang)

def get_languages():
    """Return supported languages."""
    return list(languages)


def load_opcode_sets():
    """Load opcode sets from entry points."""
    global opcode_sets
    for entry_point in iter_entry_points(group='txsc.opcodes'):
        ops_maker = entry_point.load()
        ops = ops_maker()
        if not isinstance(ops, tuple) or len(ops) != 2:
            continue
        # The name "default" is taken.
        if ops[0] == 'default' or ops[0] in opcode_sets.keys():
            continue
        # All opcode classes must be subclasses of OpCode.
        if not all(issubclass(cls, linear_nodes.OpCode) for cls in ops[1].values()):
            continue
        opcode_sets[ops[0]] = dict(ops[1])

def get_opcode_sets():
    """Return supported opcode sets."""
    return dict(opcode_sets)

def set_opcode_set(name):
    """Set the desired set of opcodes.

    This is a wrapper around txsc.linear_nodes.set_opcodes().
    """
    linear_nodes.reset_opcodes()
    d = opcode_sets[name]
    linear_nodes.set_opcodes(d)

    # Set the builtin opcode functions if any are present.
    op_funcs = []
    for cls in d.values():
        if hasattr(cls, 'func') and isinstance(cls.func, script_transformer.OpFunc):
            op_funcs.append(cls.func)
    script_transformer.reset_op_functions()
    # Extend the existing opcode functions with the custom ones.
    op_funcs = script_transformer.get_op_functions() + op_funcs
    script_transformer.set_op_functions(op_funcs)


def load_entry_points():
    """Load all entry points."""
    global _loaded
    if _loaded:
        return
    load_languages()
    load_opcode_sets()

    _loaded = True
