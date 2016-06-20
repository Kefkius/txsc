class IRError(Exception):
    """Exception raised when converting SIR instructions to the LIR."""
    pass

class IRImplicitPushError(IRError):
    """Exception raised when an implicit push is encountered."""
    pass

class IRStrictNumError(IRError):
    """Exception raised when using a non-number value in an arithmetic operation."""
    pass

class IRTypeError(IRError):
    """Exception raised when using incompatible or incorrect types."""
    pass
