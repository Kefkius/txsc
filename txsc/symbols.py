"""Symbol table implementation for languages that can use one."""

class Symbol(object):
    """A symbol."""
    def __init__(self, name=None, value=None, type_=None, mutable=False):
        self.type_ = type_
        self.name = name
        self.value = value
        self.mutable = mutable

class Scope(object):
    """A scope of symbols."""
    def __init__(self, parent):
        self.parent = parent
        self.symbols = {}

    def __str__(self):
        return str(self.symbols)

    def __getitem__(self, key):
        return self.symbols[key]

    def __setitem__(self, key, value):
        self.symbols[key] = value

    def get(self, key):
        return self.symbols.get(key)

    def clear(self):
        return self.symbols.clear()

class SymbolTable(object):
    """A symbol table."""
    # Symbol type constants.
    ByteArray = 'byte_array'
    Expr = 'expression'
    Func = 'function'
    Integer = 'integer'
    StackItem = 'stack_item'

    def __init__(self):
        self.symbols = Scope(None)
        self.scopes = [self.symbols]

    def begin_scope(self):
        self.scopes.append(Scope(self.symbols))
        self.symbols = self.scopes[-1]

    def end_scope(self):
        if self.symbols.parent is None:
            raise Exception('Already at global scope.')
        self.symbols = self.symbols.parent
        self.scopes.pop()

    def _update_mutable_symbol(self, symbol, value):
        other = self.symbols.get(symbol.name)
        if not other:
            symbol.value = [value]
            symbol.type_ = [symbol.type_]
            self.symbols[symbol.name] = symbol
        else:
            other.value.append(symbol.value)
            other.type_.append(symbol.type_)

    def insert(self, symbol):
        if symbol.mutable:
            self._update_mutable_symbol(symbol, symbol.value)
        else:
            self.symbols[symbol.name] = symbol

        symbol = self.symbols[symbol.name]

    def lookup(self, name):
        symbols = self.symbols
        symbol = symbols.get(name)
        # Search parent scopes until a symbol is found, or global scope is reached.
        while symbols.parent and not symbol:
            symbols = symbols.parent
            symbol = symbols.get(name)
        return symbol

    def clear(self):
        self.symbols = Scope(None)
        self.scopes = [self.symbols]

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
