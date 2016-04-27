"""Symbol table implementation for languages that can use one."""

class Symbol(object):
    """A symbol."""
    def __init__(self, name=None, value=None, type_=None):
        self.type_ = type_
        self.name = name
        self.value = value

class SymbolTable(object):
    """A symbol table."""
    # Symbol type constants.
    ByteArray = 'byte_array'
    Integer = 'int'
    StackItem = 'stack_item'

    def __init__(self):
        self.symbols = {}

    def insert(self, symbol):
        self.symbols[symbol.name] = symbol

    def lookup(self, name):
        return self.symbols.get(name)

    def clear(self):
        self.symbols.clear()

    def add_symbol(self, name, value, type_):
        self.insert(Symbol(name=name, value=value, type_=type_))

    def add_stack_assumptions(self, names):
        """Add assumed stack items."""
        # [(height, name), ...]
        items = [i for i in enumerate(names)]
        size = len(items)

        for height, name in items:
            depth = size - height - 1
            self.insert(Symbol(name=name, value=depth, type_=self.StackItem))
