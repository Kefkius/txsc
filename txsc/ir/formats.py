"""Utility functions to convert values between formats."""
import binascii

from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

def strip_hex(s):
    """Strip extraneous characters from s."""
    return s.replace('0x', '').replace('L', '')

def int_to_bytearray(value):
    """Encode an integer as a byte array or opcode value."""
    try:
        value = int(CScriptOp.encode_op_n(value))
    except ValueError:
        pass
    return _bignum.bn2vch(value)

def hex_to_bytearray(value):
    """Encode a hex string as a byte array."""
    value = value.replace('0x','').replace('L','')
    return binascii.unhexlify(value)


def bytearray_to_int(data, decode_small_int=True):
    """Decode a byte array into an integer.

    If decode_small_int is True, a small integer will
    be returned if data is a small int opcode.
    """
    num = _bignum.vch2bn(data)
    # Decode num if it's a small integer.
    if decode_small_int:
        try:
            return CScriptOp(num).decode_op_n()
        except Exception:
            pass
    return num

def bytearray_to_bool(data):
    return _CastToBool(data)
