"""txsc configuration.

Handles configuration values and entry points.

Entry points have the following requirements:

    - txsc.alt_stack_manager: Must return a subclass of txsc.ir.linear_runtime.AltStackManager.
    - txsc.language: Must return an instance of a txsc.language.Language subclass.
    - txsc.linear_optimizer: Must return a subclass of txsc.ir.linear_optimizer.LinearOptimizer.
    - txsc.opcode_set: Must return a subclass of txsc.ir.linear_nodes.OpCodeSet.

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

# Default opcodes, linear optimizer, and alt stack manager.
from txsc.ir import linear_nodes, linear_optimizer, linear_runtime

# Default builtin functions.
from txsc.txscript import script_transformer

# Whether entry points have been loaded.
_loaded = False
def has_loaded():
    """Return whether entry points have been loaded."""
    return _loaded


# Configurable collections.
languages = [ASMLanguage, BtcScriptLanguage, TxScriptLanguage]
alt_stack_managers = {'default': linear_runtime.AltStackManager}
opcode_sets = {'default': linear_nodes.OpCodeSet}
linear_optimizers = {'default': linear_optimizer.LinearOptimizer}


def add_language(lang):
    """Add a language."""
    # Must be a Language subclass instance.
    if not isinstance(lang, Language):
        return False
    # The language must not have a duplicate name.
    if lang.name in [i.name for i in languages]:
        return False
    languages.append(lang.__class__)
    return True

def load_languages():
    """Load languages from entry points."""
    global languages
    for entry_point in iter_entry_points(group='txsc.language'):
        lang_maker = entry_point.load()
        lang = lang_maker()
        add_language(lang)

def get_languages():
    """Return supported languages."""
    return list(languages)


def load_alt_stack_managers():
    """Load alt stack managers from entry points."""
    global alt_stack_managers
    for entry_point in iter_entry_points(group='txsc.alt_stack_manager'):
        cls_maker = entry_point.load()
        cls = cls_maker()

        if not issubclass(cls, linear_runtime.AltStackManager):
            continue
        # The name "default" is taken.
        if cls.name == 'default':
            continue
        alt_stack_managers[cls.name] = cls

def get_alt_stack_managers():
    """Return supported alt stack managers."""
    return dict(alt_stack_managers)

def set_alt_stack_manager(name):
    """Set the desired alt stack manager.

    This is a wrapper around txsc.ir.linear_runtime.set_alt_stack_manager_cls().
    """
    cls = alt_stack_managers.get(name, linear_runtime.AltStackManager)
    linear_runtime.set_alt_stack_manager_cls(cls)


def load_opcode_sets():
    """Load opcode sets from entry points."""
    global opcode_sets
    for entry_point in iter_entry_points(group='txsc.opcode_set'):
        cls_maker = entry_point.load()
        cls = cls_maker()
        if not issubclass(cls, linear_nodes.OpCodeSet):
            continue
        # The name "default" is taken.
        if cls.name == 'default':
            continue
        opcode_sets[cls.name] = cls

def get_opcode_sets():
    """Return supported opcode sets."""
    return dict(opcode_sets)

def set_opcode_set(name):
    """Set the desired set of opcodes.

    This is a wrapper around txsc.linear_nodes.set_opcode_set_cls().
    """
    cls = opcode_sets.get(name, linear_nodes.OpCodeSet)
    linear_nodes.set_opcode_set_cls(cls)

    # Set the builtin opcode functions if any are present.
    op_funcs = []
    for op_cls in cls.get_opcodes().values():
        if hasattr(op_cls, 'func') and isinstance(op_cls.func, script_transformer.OpFunc):
            op_funcs.append(op_cls.func)
    script_transformer.reset_op_functions()
    # Extend the existing opcode functions with the custom ones.
    op_funcs = script_transformer.get_op_functions() + op_funcs
    script_transformer.set_op_functions(op_funcs)


def load_linear_optimizers():
    """Load linear optimizers from entry points."""
    global linear_optimizers
    for entry_point in iter_entry_points(group='txsc.linear_optimizer'):
        cls_maker = entry_point.load()
        cls = cls_maker()
        if not issubclass(cls, linear_optimizer.LinearOptimizer):
            continue
        # The name "default" is taken.
        if cls.name == 'default':
            continue
        linear_optimizers[cls.name] = cls

def get_linear_optimizers():
    """Return supported linear optimizers."""
    return dict(linear_optimizers)

def set_linear_optimizer(name):
    """Set the desired linear optimizer.

    This is a wrapper around txsc.ir.linear_optimizer.set_linear_optimizer_cls().
    """
    cls = linear_optimizers.get(name, linear_optimizer.LinearOptimizer)
    linear_optimizer.set_linear_optimizer_cls(cls)

def load_entry_points():
    """Load all entry points."""
    global _loaded
    if _loaded:
        return
    load_languages()
    load_alt_stack_managers()
    load_opcode_sets()
    load_linear_optimizers()

    _loaded = True
