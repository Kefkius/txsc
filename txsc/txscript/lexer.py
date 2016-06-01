from ply import lex
from ply.lex import TOKEN

hexdigit = r'[0-9a-fA-F]'
implicit_hex = hexdigit + r'+'
explicit_hex = r'(0x)' + implicit_hex

tokens = ['NAME', 'NUMBER', 'HEXSTR',
        'EQUALS',
        'LBRACE', 'RBRACE',
        'LPAREN', 'RPAREN',
        'COMMA',
        'SEMICOLON',

        # Conditionals.
        'IF',
        'ELSE',

        # Arithmetic operators.
        'PLUS', 'MINUS',
        'TIMES', 'DIVIDE',
        'MOD',
        'LSHIFT', 'RSHIFT',

        # Bitwise operators.
        'AMPERSAND', 'CARET', 'PIPE', 'TILDE',

        # Comparison operators.
        'EQUALITY', 'INEQUALITY',
        'LESSTHAN', 'GREATERTHAN',
        'LESSTHANOREQUAL', 'GREATERTHANOREQUAL',

        # Reserved words.
        'ASSUME',
        'FUNC',
        'MUTABLE',
        'RETURN',
        'VERIFY',
        'AND',
        'OR',
        'NOT',

        # Declarations.
        'LET',
]

reserved_words = {
    'assume': 'ASSUME',
    'if': 'IF',
    'else': 'ELSE',
    'func': 'FUNC',
    'mutable': 'MUTABLE',
    'return': 'RETURN',
    'verify': 'VERIFY',

    'and': 'AND',
    'or': 'OR',
    'not': 'NOT',

    'let': 'LET',
}

t_ignore = ' \t'

t_PLUS = r'\+'
t_MINUS = r'\-'
t_TIMES = r'\*'
t_DIVIDE = r'\/'
t_MOD = r'\%'
t_LSHIFT = r'\<\<'
t_RSHIFT = r'\>\>'

t_AMPERSAND = r'\&'
t_CARET = r'\^'
t_PIPE = r'\|'
t_TILDE = r'\~'

t_EQUALITY = r'\=\='
t_INEQUALITY = r'\!\='
t_LESSTHAN = r'\<'
t_GREATERTHAN = r'\>'
t_LESSTHANOREQUAL = r'\<\='
t_GREATERTHANOREQUAL = r'\>\='

t_EQUALS = r'\='
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_COMMA = r'\,'
t_SEMICOLON = r'\;'

t_ASSUME = r'assume'
t_IF = r'if'
t_ELSE = r'else'
t_FUNC = r'func'
t_MUTABLE = r'mutable'
t_RETURN = r'return'
t_VERIFY = r'verify'
t_AND = r'and'
t_OR = r'or'

t_LET = r'let'

def t_NAME(t):
    r'[a-zA-Z][a-zA-Z0-9_]*'
    t.type = reserved_words.get(t.value, 'NAME')
    return t

@TOKEN(r'(' + explicit_hex + r')|(\d+)')
def t_NUMBER(t):
    is_hex = t.value.startswith('0x')
    try:
        t.value = int(t.value, 16 if is_hex else 10)
    except ValueError:
        print("Line %d: Number %s is too large!" % (t.lineno, t.value))
    return t

@TOKEN(r'\'' + implicit_hex + r'\'')
def t_HEXSTR(t):
    return t

def t_COMMENT(t):
    r'\#.*'
    pass

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print("Illegal character '%s'" % t.value[0])

precedence = (
    ('left', 'EQUALITY', 'INEQUALITY',),
    ('left', 'LESSTHAN', 'GREATERTHAN', 'LESSTHANOREQUAL', 'GREATERTHANOREQUAL',),
    ('left', 'LSHIFT', 'RSHIFT',),
    ('left', 'PLUS', 'MINUS',),
    ('left', 'TIMES', 'DIVIDE', 'MOD',),
    ('right', 'UNARYOP',),
)

