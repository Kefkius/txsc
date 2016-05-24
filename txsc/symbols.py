"""Symbol table implementation for languages that can use one."""
import copy

class SymbolType(object):
    """Symbol types."""
    ByteArray = 'byte_array'
    Expr = 'expression'
    Func = 'function'
    Integer = 'integer'
    StackItem = 'stack_item'
    Symbol = 'symbol'

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

    def __iter__(self):
        for v in self.symbols.values():
            yield v

    def get(self, key):
        return self.symbols.get(key)

    def clear(self):
        return self.symbols.clear()

class GlobalScope(Scope):
    """The global scope."""
    def __init__(self):
        super(GlobalScope, self).__init__(None)

class SymbolTable(object):
    """A symbol table."""

    def __init__(self):
        self.symbols = GlobalScope()
        self.scopes = [self.symbols]

    @classmethod
    def clone(cls, other):
        """Create a new symbol table from a symbol table."""
        scope_index = other.scopes.index(other.symbols)
        scopes = copy.deepcopy(other.scopes)
        symtable = cls()
        symtable.scopes = scopes
        symtable.symbols = symtable.scopes[scope_index]
        return symtable

    def is_global_scope(self):
        """Get whether the current scope is the global scope."""
        return isinstance(self.symbols, GlobalScope)

    def iter_symbols(self):
        symbols = self.symbols
        while symbols:
            iterator = iter(symbols)
            for value in iterator:
                yield value
            symbols = symbols.parent

    def begin_scope(self):
        self.scopes.append(Scope(self.symbols))
        self.symbols = self.scopes[-1]

    def end_scope(self):
        if self.symbols.parent is None:
            raise Exception('Already at global scope.')
        self.symbols = self.symbols.parent

    def insert(self, symbol):
        # Check for assignment to immutables in the current scope.
        if self.symbols.get(symbol.name):
            other = self.symbols[symbol.name]
            if not other.mutable:
                raise Exception('Cannot assign value to immutable "%s"' % (other.name))
            else:
                symbol.mutable = True
        self.symbols[symbol.name] = symbol

    def lookup(self, name):
        symbols = self.symbols
        symbol = symbols.get(name)
        # Search parent scopes until a symbol is found, or global scope is reached.
        while symbols.parent and not symbol:
            symbols = symbols.parent
            symbol = symbols.get(name)
        return symbol

    def clear(self):
        self.symbols = GlobalScope()
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
            self.insert(Symbol(name=name, value=depth, type_=SymbolType.StackItem, mutable=False))

    def add_function_def(self, func_def):
        """Add a function definition."""
        if not self.is_global_scope():
            raise Exception('Functions can only be defined in the global scope')
        self.insert(Symbol(name=func_def.name, value=func_def, type_=SymbolType.Func, mutable=False))
