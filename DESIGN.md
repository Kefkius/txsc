# Design

## Compilation

`txsc` compiles scripts to/from languages using an intermediate representation.
The nodes of this representation can be found in `txsc.linear_nodes`, and the
container for them can be found in `txsc.instructions`.

## Languages

`txsc` organizes languages as packages (or modules for small languages). Each
language package/module contains a class that is a subclass of `Language`.

A subclass of `Language` has a class attribute, `name`, used to identify it.
It also has two optional class attributes:

- `source_visitor`: A class that can transform source into instructions.
- `target_visitor`: A class that can transform instructions into source.

If a language has a `source_visitor`, it can process input. If it has a `target_visitor`,
it can process instructions and output source. If a language has neither of these attributes,
it cannot be used.

The base classes of `source_visitor` and `target_visitor` can be found in `txsc.transformer`.

`txsc` also support Python *entry points* which can be used to add new languages via plugins.
