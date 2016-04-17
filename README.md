# txsc

txsc is a Bitcoin script compiler.

## Usage

Run `setup.py install`. The script `txsc` (which refers to `txsc.compiler.py`) will be installed.
You can also run `compiler.py` locally, but you won't be able to use any languages added by plugins.

Unless specified, `txsc` will assume that the source language is `txscript` and the target
language is `BTC` (see below for explanations of what these languages are).

You can either invoke `txsc` with a string or with a filename.

Compile `txscript` to `BTC` and `ASM`:

```
$ txsc "2 + 5 == 7"
5255935787
$ txsc "2 + 5 == 7" -t asm
2 5 ADD 7 EQUAL
```

With `-v`, optimizations will be shown:

```
$ txsc "verify 2 + 5 == 7" -t asm -v
Linear Intermediate Representation:
  ['OP_2', 'OP_5', 'OP_ADD', 'OP_7', 'OP_EQUAL', 'OP_VERIFY']

Optimized Linear Representation:
  ['OP_2', 'OP_5', 'OP_ADD', 'OP_7', 'OP_EQUALVERIFY']

asm:
  2 5 ADD 7 EQUALVERIFY
```

## Languages

### ASM

`ASM` represents a script as assembly instructions. Data pushes are hex-encoded, and prefixed with
their size.

### BTC

`BTC` refers to the raw, hex-encoded script format that Bitcoin scripts are sometimes represented as.

### TxScript

`txsc` includes a language used to construct transaction scripts. It's essentially a subset of Python.
See the package `txsc.txscript` for its source. It works by parsing Python code and generating a
structural intermediate representation, then transforming that into the linear intermediate representation
that other languages can use.

## Credits

txsc is based loosely on [Superscript compiler](https://github.com/curiosity-driven/bitcoin-contracts-compiler), an educational Bitcoin script compiler.
