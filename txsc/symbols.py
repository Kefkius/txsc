"""Symbol table implementation for languages that can use one."""
import ast

class Symbol(ast.Str):
    """Base symbol class."""
    _fields = ('name',)

class StackItem(Symbol):
    """Assumed stack item"""
    _fields = ('name', 'depth', 'stack_size')

class SymbolTable(object):
    """A symbol table."""
    def __init__(self):
        self.symbols = {}

    def insert(self, symbol):
        self.symbols[symbol.name] = symbol

    def lookup(self, name):
        return self.symbols.get(name)

    def clear(self):
        self.symbols.clear()

    def add_stack_assumptions(self, names):
        """Add assumed stack items."""
        # [(height, name), ...]
        items = [i for i in enumerate(names)]
        size = len(items)

        for height, name in items:
            depth = size - height - 1
            self.insert(StackItem(name=name, depth=depth, stack_size=size))
