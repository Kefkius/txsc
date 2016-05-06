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
