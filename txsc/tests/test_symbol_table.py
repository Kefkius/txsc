import unittest

from txsc.symbols import SymbolTable, SymbolType, Symbol

class SymbolTest(unittest.TestCase):
    def test_equality(self):
        symbol_0_0 = Symbol(name='foo', value=1, type_=SymbolType.Integer, mutable=False)
        symbol_0_1 = Symbol(name='foo', value=1, type_=SymbolType.Integer, mutable=False)
        symbol_1_0 = Symbol(name='foo', value=1, type_=SymbolType.Integer, mutable=True)

        self.assertEqual(symbol_0_0, symbol_0_1)
        self.assertNotEqual(symbol_0_0, symbol_1_0)

class BaseSymbolsTest(unittest.TestCase):
    """Base class for SymbolTable tests."""
    def setUp(self):
        self.symbol_table = SymbolTable()


class SymbolsTest(BaseSymbolsTest):
    def setUp(self):
        super(SymbolsTest, self).setUp()
        self.symbol_table.insert(Symbol(name='foo', value=1, type_=SymbolType.Integer, mutable=False), declaration=True)

    def test_add_symbol(self):
        self.symbol_table.add_symbol('bar', 2, SymbolType.Integer, mutable=False, declaration=True)
        symbol = self.symbol_table.lookup('bar')
        self.assertEqual('bar', symbol.name)
        self.assertEqual(2, symbol.value)
        self.assertEqual(SymbolType.Integer, symbol.type_)
        self.assertEqual(False, symbol.mutable)

    def test_dump(self):
        self.assertEqual({'foo': 'immutable integer foo = 1'}, self.symbol_table.symbols.dump())

    def test_lookup(self):
        symbol = self.symbol_table.lookup('foo')
        self.assertEqual('foo', symbol.name)
        self.assertEqual(1, symbol.value)
        self.assertEqual(SymbolType.Integer, symbol.type_)
        self.assertEqual(False, symbol.mutable)

class ScopesTest(BaseSymbolsTest):
    def setUp(self):
        """Add a global symbol, begin a new scope, and add a symbol to it."""
        super(ScopesTest, self).setUp()
        self.symbol_table.insert(Symbol(name='scope_0_symbol', value=0, type_=SymbolType.Integer, mutable=False), declaration=True)
        self.symbol_table.begin_scope()
        self.symbol_table.insert(Symbol(name='scope_1_symbol', value=1, type_=SymbolType.Integer, mutable=False), declaration=True)

    def test_lookup_global_symbol(self):
        expected = Symbol(name='scope_0_symbol', value=0, type_=SymbolType.Integer, mutable=False)
        # Search current and parent scopes.
        self.assertEqual(expected, self.symbol_table.lookup('scope_0_symbol'))
        # Search global scope only.
        self.assertEqual(expected, self.symbol_table.lookup_global('scope_0_symbol'))
        # Search only current scope.
        self.assertIsNone(self.symbol_table.lookup('scope_0_symbol', one_scope=True))

    def test_insert_global_symbol(self):
        expected = Symbol(name='scope_0_symbol', value=0, type_=SymbolType.Integer, mutable=False)
        self.symbol_table.insert_global(expected)
        self.symbol_table.end_scope()
        self.assertEqual(expected, self.symbol_table.lookup('scope_0_symbol'))
        self.assertEqual(expected, self.symbol_table.lookup('scope_0_symbol', one_scope=True))
