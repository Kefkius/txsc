"""Symbol table implementation for languages that can use one."""

class Symbol(object):
    """A symbol."""
    def __init__(self, name=None, value=None, type_=None, mutable=False):
        self.type_ = type_
        self.name = name
        self.value = value
        self.mutable = mutable

class SymbolTable(object):
    """A symbol table."""
    # Symbol type constants.
    ByteArray = 'byte_array'
    Expr = 'expression'
    Integer = 'integer'
    StackItem = 'stack_item'

    def __init__(self):
        self.symbols = {}

    def _update_mutable_symbol(self, symbol, value):
        other = self.symbols.get(symbol.name)
        if not other:
            symbol.value = [value]
            self.symbols[symbol.name] = symbol
        else:
            other.value.append(symbol.value)

    def insert(self, symbol):
        if symbol.mutable:
            self._update_mutable_symbol(symbol, symbol.value)
        else:
            self.symbols[symbol.name] = symbol

        symbol = self.symbols[symbol.name]

    def lookup(self, name):
        return self.symbols.get(name)

    def clear(self):
        self.symbols.clear()

    def add_symbol(self, name, value, type_, mutable=False):
        self.insert(Symbol(name=name, value=value, type_=type_, mutable=mutable))

    def add_stack_assumptions(self, names):
        """Add assumed stack items."""
        # [(height, name), ...]
        items = [i for i in enumerate(names)]
        size = len(items)

        for height, name in items:
            depth = size - height - 1
            self.insert(Symbol(name=name, value=depth, type_=self.StackItem, mutable=False))
