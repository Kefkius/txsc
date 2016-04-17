from ply import lex, yacc

class ASMParser(object):
    def __init__(self):
        self.lexer = lex.lex(module=self)
        # Suppress warning that OP is (technically) unused.
        self.parser = yacc.yacc(module=self, errorlog=yacc.NullLogger())

    def parse_source(self, src):
        return self.parser.parse(src, lexer=self.lexer)


    tokens = ('OP', 'PUSH', 'OPCODE')

    t_ignore = ' \t\n'

    def t_OP(self, t):
        r'[a-zA-Z0-9_]+'
        if t.value.startswith('0x'):
            t.type = 'PUSH'
        else:
            t.type = 'OPCODE'
        return t

    def t_error(self, t):
        print("Illegal character '%s'" % t.value)


    def p_error(self, p):
        raise SyntaxError('Syntax error: %s' % p)

    def p_script(self, p):
        '''script : word
                  | script word
        '''
        if isinstance(p[1], list):
            p[0] = p[1]
            p[0].append(p[2])
        else:
            p[0] = [p[1]]

    def p_word_push(self, p):
        '''word : PUSH PUSH'''
        p[0] = int(p[2], 16)

    def p_word_opcode(self, p):
        '''word : OPCODE'''
        p[0] = p[1]
