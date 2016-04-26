
class Language(object):
    """A language that source may be written in.


    Attributes:
        - source_visitor: A class that converts from a language to Instructions.
        - target_visitor: A class that converts from Instructions to a language.
        - supports_symbol_table (bool): Whether this language supports symbols.

    """
    name = ''
    source_visitor = None
    target_visitor = None
    supports_symbol_table = False

    @classmethod
    def has_source_visitor(cls):
        return cls.source_visitor is not None

    @classmethod
    def has_target_visitor(cls):
        return cls.target_visitor is not None

    def process_source(self, *args):
        if not self.has_source_visitor():
            raise NotImplementedError()
        visitor = self.source_visitor()
        return visitor.transform(*args)

    def compile_instructions(self, *args):
        if not self.has_target_visitor():
            raise NotImplementedError()
        visitor = self.target_visitor()
        return visitor.compile(*args)
