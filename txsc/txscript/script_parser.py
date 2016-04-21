import ast

from ply import lex, yacc

import lexer

class ScriptParser(object):
    tokens = lexer.tokens
    precedence = lexer.precedence

    def __init__(self, **kwargs):
        self.debug = False
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.lexer = lex.lex(module=lexer)
        self.parser = yacc.yacc(module=self, debug=self.debug)
        self.symbol_table = None

    def parse(self, s, symbol_table):
        self.symbol_table = symbol_table
        return self.parser.parse(s, lexer=self.lexer)

    def p_error(self, p):
        raise SyntaxError('Syntax error: %s' % p)

    def p_module(self, p):
        '''module : expr
                  | statement
                  | module SEMICOLON expr
                  | module SEMICOLON statement
                  | module SEMICOLON
        '''
        if isinstance(p[1], ast.Module):
            p[0] = p[1]
        else:
            p[0] = ast.Module(body=[p[1]])

        if len(p) > 3:
            p[0].body.append(p[3])

    def p_statement_assign(self, p):
        '''statement : NAME EQUALS expr'''
        if self.debug: print('statement : NAME = expr; %s, %s' % (p[1], p[3]))
        p[0] = ast.Assign(targets=[
            ast.Name(id=p[1], ctx=ast.Store()),
        ], value=p[3])

    def p_function_args(self, p):
        '''args : expr
                | args COMMA expr
        '''
        args = [p[1]]
        if hasattr(p[1], 'elts'):
            args = p[1].elts
        if len(p) > 2:
            args.append(p[3])
        p[0] = ast.List(elts=args, ctx=ast.Store())

    def p_assume(self, p):
        '''expr : ASSUME args'''
        self.symbol_table.add_stack_assumptions([i.id for i in p[2].elts])
        p[0] = ast.Pass()
        return

    def p_function_call(self, p):
        '''expr : NAME LPAREN args RPAREN'''
        p[0] = ast.Call(func=ast.Name(id=p[1], ctx=ast.Load()),
                args=p[3].elts,
                keywords=[])

    def p_expr_unaryop(self, p):
        '''expr : MINUS expr %prec UNARYOP
                | TILDE expr %prec UNARYOP
        '''
        op = None
        if p[1] == '-':
            op = ast.USub()
        elif p[1] == '~':
            op = ast.Invert()

        p[0] = ast.UnaryOp(op=op, operand=p[2])

    def p_verify(self, p):
        '''expr : VERIFY expr'''
        p[0] = ast.Assert(test=p[2], msg=None)

    def p_expr_binop(self, p):
        '''expr : expr PLUS expr
                | expr MINUS expr
                | expr TIMES expr
                | expr DIVIDE expr
                | expr MOD expr
                | expr LSHIFT expr
                | expr RSHIFT expr
        '''
        op = None
        if p[2] == '+':
            op = ast.Add()
        elif p[2] == '-':
            op = ast.Sub()
        elif p[2] == '*':
            op = ast.Mult()
        elif p[2] == '/':
            op = ast.Div()
        elif p[2] == '%':
            op = ast.Mod()
        elif p[2] == '<<':
            op = ast.LShift()
        elif p[2] == '>>':
            op = ast.RShift()

        p[0] = ast.BinOp(left=p[1], op=op, right=p[3])

    def p_expr_compare(self, p):
        '''expr : expr EQUALITY expr
                | expr INEQUALITY expr
                | expr LESSTHAN expr
                | expr GREATERTHAN expr
                | expr LESSTHANOREQUAL expr
                | expr GREATERTHANOREQUAL expr
        '''
        op = None
        if p[2] == '==':
            op = ast.Eq()
        elif p[2] == '!=':
            op = ast.NotEq()
        elif p[2] == '<':
            op = ast.Lt()
        elif p[2] == '>':
            op = ast.Gt()
        elif p[2] == '<=':
            op = ast.LtE()
        elif p[2] == '>=':
            op = ast.GtE()

        p[0] = ast.Compare(left=p[1], ops=[op], comparators=[p[3]])

    def p_expr_name(self, p):
        '''expr : NAME'''
        if self.debug: print('expr : NAME')
        p[0] = ast.Name(id=p[1], ctx=ast.Load())

    def p_expr_group(self, p):
        '''expr : LPAREN expr RPAREN'''
        p[0] = p[2]

    def p_expr_number(self, p):
        '''expr : NUMBER'''
        if self.debug: print('expr : NUMBER %s' % p[1])
        p[0] = ast.Num(n=p[1])

    def p_statement_expr(self, p):
        '''statement : expr'''
        p[0] = p[1]

