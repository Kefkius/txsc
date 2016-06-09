# txsc

[![Join the chat at https://gitter.im/Kefkius/txsc](https://badges.gitter.im/Kefkius/txsc.svg)](https://gitter.im/Kefkius/txsc?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

txsc (**tx** **s**cript **c**ompiler) is a Bitcoin transaction script compiler.

## Usage

Run `setup.py install`. The script `txsc` (which refers to `txsc.compiler.py`) will be installed.
You can also run `compiler.py` locally, but you won't be able to use any languages added by plugins.

Unless specified, `txsc` will assume that the source language is `txscript` and the target
language is `BTC` (see below for explanations of what these languages are).

You can either invoke `txsc` with a string or with a filename. If a filename is specified, the file
extension will be used to determine the source language if one is present.

Compile raw `BTC` to `ASM`:

```
txsc "5255935788" -s btc -t asm
2 5 ADD 7 EQUALVERIFY
```

Compile `txscript` to `BTC` and `ASM`:

```
$ txsc "2 + 5 == 7;"
5255935787
$ txsc "2 + 5 == 7;" -t asm
2 5 ADD 7 EQUAL
```

With `-v`, optimizations will be shown:

```
$ txsc "verify 2 + 5 == 7;" -t asm -v
Linear Intermediate Representation:
  ['OP_2', 'OP_5', 'OP_ADD', 'OP_7', 'OP_EQUAL', 'OP_VERIFY']

Optimized Linear Representation:
  ['OP_2', 'OP_5', 'OP_ADD', 'OP_7', 'OP_EQUALVERIFY']

asm:
  2 5 ADD 7 EQUALVERIFY
```

## Configuration Files

If a file called `txsc.conf` exists in the directory that `txsc` is being run in, it will be loaded by the compiler. A configuration
file may also exist at `$HOME/.config/txsc/txsc.conf`. If the command-line option `--config` is supplied, it will be used instead of
these paths. The configuration file is in JSON format. Options in the configuration file are overriden by command-line options.

Here is a sample of what a configuration file may look like:

```
{
    "log_level": "error",
    "target_lang": "asm"
}
```

The above configuration file specifies that only errors should be logged, and that `asm` is the target language to compile source to.

## Languages

### ASM

`ASM` represents a script as assembly instructions. Data pushes are hex-encoded, and prefixed with
their size.

### BTC

`BTC` refers to the raw, hex-encoded script format that Bitcoin scripts are sometimes represented as.

### TxScript

`txsc` includes a language used to construct transaction scripts. It's based on Python.
It works by parsing code and generating a structural intermediate representation,
then transforming that into the linear intermediate representation that other languages can use.

See the file `txscript` in the `doc` directory for more information about TxScript.

## Examples

See the *examples* folder for scripts that `txsc` can be called with directly.

## Credits

txsc is based loosely on [Superscript compiler](https://github.com/curiosity-driven/bitcoin-contracts-compiler), an educational Bitcoin script compiler.
