"""Utility functions to convert values between formats."""
import binascii

import hexs

from bitcoin import base58
from bitcoin.core import _bignum
from bitcoin.core.script import CScriptOp
from bitcoin.core.scripteval import _CastToBool

def hex_to_list(s):
    """Create a list of the bytes in s."""
    s = hexs.format_hex(s)
    return [s[i:i+2] for i in range(0, len(s), 2)]

def int_to_bytearray(value, as_opcode=True):
    """Encode an integer as a byte array or opcode value."""
    if as_opcode:
        try:
            value = int(CScriptOp.encode_op_n(value))
        except ValueError:
            pass
    return _bignum.bn2vch(value)[::-1]

def int_to_hex(value):
    """Encode an integer as a hex string.

    This is a convenience function that calls int_to_bytearray().
    """
    return int_to_bytearray(value, as_opcode=False).encode('hex')

def hex_to_bytearray(value):
    """Encode a hex string as a byte array.

    This does not account for Bitcoin's encoding of negative numbers.
    """
    return hexs.format_hex(value).decode('hex')

def bytearray_to_int(data, decode_small_int=True):
    """Decode a byte array into an integer.

    If decode_small_int is True, a small integer will
    be returned if data is a small int opcode.
    """
    num = _bignum.vch2bn(data[::-1])
    # Decode num if it's a small integer.
    if decode_small_int:
        try:
            return CScriptOp(num).decode_op_n()
        except Exception:
            pass
    return num

def hex_to_int(data):
    """Decode a hex string into an integer."""
    return bytearray_to_int(hex_to_bytearray(data))

def bytearray_to_bool(data):
    return _CastToBool(data)

def address_to_bytearray(s):
    """Decode a base58 address into a bytearray."""
    return base58.CBase58Data(s).to_bytes()

max_int_32 = (1 << 31) - 1
min_int_32 = -1 << 31
def is_strict_num(value):
    """Return whether value is limited to 4 bytes."""
    val = min(value, max_int_32)
    val = max(val, min_int_32)
    return val == value
