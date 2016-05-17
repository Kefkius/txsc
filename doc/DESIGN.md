# Design

## Compilation

`txsc` compiles scripts to/from languages using intermediate representations.
There are two intermediate representations: One that is structural, and one that is linear.

The structural representation is higher-level and is structued as a tree.
The linear representation is lower-level and is the representation that ultimately
gets compiled.

These representations can be found in `txsc.ir`.

## Languages

`txsc` organizes languages as packages (or modules for small languages). Each
language package/module contains a class that is a subclass of `Language`.

A subclass of `Language` has a class attribute, `name`, used to identify it.
It also has two optional class attributes:

- `source_visitor`: A class that can transform source into instructions.
- `target_visitor`: A class that can transform instructions into source.
- `supports_symbol_table`: Whether or not the language supports symbols.

If a language has a `source_visitor`, it can process input. If it has a `target_visitor`,
it can process instructions and output source. If a language has neither of these attributes,
it cannot be used.

The base classes of `source_visitor` and `target_visitor` can be found in `txsc.transformer`.
`SourceVisitor` subclasses can specify the type of intermediate representation they produce
via the class attribute `ir_type`. By default, it is expected that a linear representation
will be produced.

`txsc` also support Python *entry points* which can be used to add new languages via plugins.


## Optimization

Optimization entails lowering the number of opcodes used in a script.
This primarily means reducing the number of operations performed, and moving assumed stack values
closer to the beginning of the script so that they can more easily access the values they represent.

Optimization happens at two different levels:

- Structural representation optimization.
- Linear representation optimization.

### Structural IR Optimizations

The structural IR allows for some particular optimizations to be performed. Some operations are
commutative (i.e. the order of operands does not matter), and `txsc` takes advantage of this by
commuting operands in certain situations. If an assumed stack item and a constant value are operands
for a commutative operation, the assumed stack item will be commuted to the left side of that operation.

Also, if two instances of the same commutative operation are performed consecutively, their
operands will likewise be commuted.

#### Examples

In the following examples, assume that `a` represents a stack assumption, and that `a` is the
only stack assumption in the script.

- `2 + a` will be commuted to `a + 2`. The result is that when translating the structural
representation to the linear one, the corresponding opcodes will be `2 ADD` because the value
of `a` is assumed to precede the value `2`.

- `2 + a + 3` will be commuted to `a + 2 + 3`. When translating the structural representation
to the linear one, the corresponding opcodes will be `2 3 ADD ADD`. This has the same number of opcodes
as if only commuting of operands in the same operation was performed (`2 ADD 3 ADD`). However,
if evaluation of constant expressions is enabled (which depends on the optimization level passed to `txsc`),
then it will be shortened to `5 ADD`. This could not otherwise be evaluated as a constant expression,
since `2 + a` and `a + 3` are not constant expressions.

### Linear IR Optimizations

The linear IR has its own optimizations. These are primarily peephole optimizations, which replace
opcodes that do not depend on their context.

These optimizations take advantage of the fact that some sequences of opcodes can be shortened using
other opcodes. Arithmetic shortcut opcodes such as `2MUL` and `2DIV` are some examples.
Stack manipulation opcodes can also often be optimized. Particularly, the opcodes `PICK` and `ROLL`
(which copy or move a given stack item to the top, respectively) can sometimes be replaced with shortcut opcodes.

#### Examples

- `5 1 ADD` will be optimized into `5 1ADD`.
- `5 2 MUL` will be optimized into `5 2MUL`.
- `0 PICK` will be optimized into `DUP`.
- `0 ROLL` will be removed from the script.
- `1 PICK` will be optimized into `OVER`.
- `1 ROLL` will be optimized into `SWAP`.
