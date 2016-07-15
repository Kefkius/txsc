"""Symbol table implementation for languages that can use one."""
import copy

class StackItemValue(object):
    def __init__(self, depth=0, height=0):
        self.depth = depth
        self.height = height

class ImmutableError(Exception):
    """Exception raised when attempting to replace an immutable value."""
    pass

class MultipleDeclarationsError(Exception):
    """Exception raised when there are multiple declarations of a symbol in one scope."""
    pass

class UndeclaredError(Exception):
    """Exception raised when using an undeclared symbol."""
    pass

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

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        mutable = 'mutable' if self.mutable else 'immutable'
        return '%s %s %s = %s' % (mutable, self.type_, self.name, self.value)

class ScopeType(object):
    """Scope types."""
    Conditional = 'conditional'
    Function = 'function'
    General = 'general'

class Scope(object):
    """A scope of symbols."""
    def __init__(self, parent, scope_type=ScopeType.General):
        self.parent = parent
        self.scope_type = scope_type
        self.symbols = {}

    def __str__(self):
        return str(self.symbols)

    def __getitem__(self, key):
        return self.symbols[key]

    def __setitem__(self, key, value):
        self.symbols[key] = value

    def __delitem__(self, key):
        del self.symbols[key]

    def __iter__(self):
        for v in self.symbols.values():
            yield v

    def get(self, key):
        return self.symbols.get(key)

    def clear(self):
        return self.symbols.clear()

    def dump(self):
        return {k: str(v) for k, v in self.symbols.items()}

class GlobalScope(Scope):
    """The global scope."""
    def __init__(self):
        super(GlobalScope, self).__init__(None)

class SymbolTable(object):
    """A symbol table."""

    def __init__(self):
        self.clear()

    def clear(self):
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

    def get_global_scope(self):
        """Get the global scope."""
        global_scope = self.scopes[0]
        if not isinstance(global_scope, GlobalScope):
            raise Exception('No global scope exists.')
        return global_scope

    def iter_symbols(self):
        symbols = self.symbols
        while symbols:
            iterator = iter(symbols)
            for value in iterator:
                yield value
            symbols = symbols.parent

    def begin_scope(self, scope_type=ScopeType.General):
        self.scopes.append(Scope(self.symbols, scope_type=scope_type))
        self.symbols = self.scopes[-1]

    def end_scope(self):
        if self.symbols.parent is None:
            raise Exception('Already at global scope.')
        self.symbols = self.symbols.parent

    def _check_function(self, symbol):
        """Validate a function before it is inserted."""
        # Functions cannot be mutable.
        if symbol.mutable:
            raise Exception('Functions cannot be mutable.')
        # Functions can only be defined in the global scope.
        if not self.is_global_scope():
            raise Exception('Functions can only be defined in the global scope.')

    def check_symbol(self, symbol, declaration):
        """Validate symbol before it is inserted.

        An exception is raised if it is invalid.
        """
        # Make sure this symbol was declared.
        if not declaration and not self.lookup(symbol.name):
            raise UndeclaredError('Symbol "%s" was not declared.' % symbol.name)

        if symbol.type_ == SymbolType.Func:
            self._check_function(symbol)

        if self.symbols.get(symbol.name):
            # Check for multiple declarations in the current scope.
            if declaration:
                raise MultipleDeclarationsError('Symbol "%s" was already declared.' % symbol.name)
            other = self.symbols[symbol.name]
            # Check for assignment to an immutable in the current scope.
            if not other.mutable:
                raise ImmutableError('Cannot assign value to immutable symbol "%s".' % other.name)
            else:
                symbol.mutable = True

    def insert(self, symbol, declaration=False):
        self.check_symbol(symbol, declaration)
        self.symbols[symbol.name] = symbol

    def insert_global(self, symbol):
        """Insert a symbol into the global scope."""
        self.get_global_scope()[symbol.name] = symbol

    def lookup(self, name, one_scope=False):
        symbols = self.symbols
        symbol = symbols.get(name)
        if one_scope:
            return symbol
        # Search parent scopes until a symbol is found, or global scope is reached.
        while symbols.parent and not symbol:
            symbols = symbols.parent
            symbol = symbols.get(name)
        return symbol

    def lookup_global(self, name):
        """Lookup a symbol in the global scope."""
        return self.get_global_scope().get(name)

    def delete(self, name, one_scope=False, all_scopes=True):
        """Delete a symbol.

        If all_scopes is True, the symbol will be deleted from
        the current scope and all parent scopes.
        """
        symbols = self.symbols
        symbol = symbols.get(name)
        if symbol:
            del symbols[name]
        if one_scope:
            return
        # Search parent scopes and delete symbols in them.
        while symbols.parent:
            symbols = symbols.parent
            symbol = symbols.get(name)
            if symbol:
                del symbols[name]
                if not all_scopes:
                    break

    def delete_global(self, name):
        """Delete a symbol in the global scope."""
        if self.get_global_scope().get(name):
            del self.get_global_scope()[name]

    def add_symbol(self, name, value, type_, mutable=False, declaration=False):
        self.insert(Symbol(name=name, value=value, type_=type_, mutable=mutable), declaration=declaration)

    def add_stack_assumptions(self, names):
        """Add assumed stack items."""
        # [(height, name), ...]
        items = [i for i in enumerate(names)]
        size = len(items)

        for height, name in items:
            depth = size - height - 1
            value = StackItemValue(depth, height)
            self.insert(Symbol(name=name, value=value, type_=SymbolType.StackItem, mutable=False), declaration=True)
        self.insert(Symbol(name='_stack_names', value=list(names), type_=SymbolType.Expr, mutable=False), declaration=True)

    def add_function_def(self, func_def):
        """Add a function definition."""
        self.insert(Symbol(name=func_def.name, value=func_def, type_=SymbolType.Func, mutable=False), declaration=True)
