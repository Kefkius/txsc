# TxScript

TxScript is a language made for constructing transaction scripts. It is expression-oriented
in that nearly every language construct changes the state of the stack.

## Syntax

TxScript source code is comprised of one or more statements. Statements in this sense also
encompass expressions.
Every statement must end with a semicolon (`;`). Whitespace is ignored.

### Comments

Comments are denoted by a pound sign (`#`).

```
# This is a comment.
```

### Literals

Literal values in TxScript are either integers or hex strings. Hex strings are enclosed in single quotation marks, with no "0x" prefix.

```
# The RIPEMD-160 hash of my public key.
let myHash = '1111111111111111111111111111111111111111';
```

### Assignments

TxScript supports immutable and mutable assignments. To bind an immutable name to a value, use the equals sign (`=`).
To bind a mutable name to a value, use the keyword `mutable` before the name.

Names can be bound to literal values or expressions. If bound to an expression, txsc will attempt to evaluate it during optimization.
Names may not begin with an underscore or a number.

The first time a name is declared, the keyword `let` must be used.

```
let myVar = 5 + 12;
let mutable myOtherVar = 9;
myOtherVar = 2;
```

### Conditionals

Conditional statements are denoted as follows: `if <expression> {body}`. An `else` statement can be specified as well:
`if <expression> {body} else {elsebody}`.

```
let myVar = 5;
if myVar == 5 {
    myVar * 2;
} else {
    myVar / 2;
}
```

There is a drawback to using conditionals: If the two execution paths of a conditional do not result in the same number of stack
items being present, then stack assumptions (see below) cannot be used after the conditional. The reason for this is that the number
of items between a stack assumption and the actual assumed stack item cannot be determined this way.

### Built-in Functions

There are built-in functions for opcodes. They are named using camelCase conventions.

```
let myVar = 2 + 5;
verify min(myVar, 10) == myVar;
```

### Inner Scripts

TxScript supports "inner scripts," which are scripts within a script. The most relevant example is in Pay-To-Script-Hash
redeem scripts, which are serialized scripts that are executed during P2SH spending.

Inner scripts are created with the built-in function `raw()`. Every argument passed to `raw()` is an expression.

```
raw(2 + 5, 3 + 6);
```

### Defining Functions

Functions can be defined in a script. This is done using the keyword `func`:

```
func addFive(x) {
    x + 5;
}
```

## Keywords

The following keywords have meaning in txscript scripts.

| Keyword   | Meaning       |
| --------- | ------------- |
| assume    | Declare assumed stack values by name. |
| func      | Define a function.|
| let       | Declare a new name. |
| mutable   | Declare a mutable name. |
| return    | Marks the script as invalid. |
| verify    | Fail if the expression that follows is not true. |
| and       | Logical AND operator. |
| or        | Logical OR operator. |
| if        | Begin an `if` statement. |
| else      | Begin an `else` statement. |

### Assumptions

Since TxScript is made for transaction scripts, there is a keyword used to signify that you *assume*
a number of values will already be on the stack when your script begins execution.

For example, a Pay-to-Public-Key-Hash transaction output script expects two stack items to be present when it begines execution:
A signature and a public key.

```
assume sig, pubkey;
```

You can then use the words `sig` and `pubkey` in your script to refer to these expected stack items. Assumption statements
are internally treated as assignments.

### Return

The `return` keyword marks the script as invalid. This makes a given transaction output provably unspendable. It is often
used to add arbitrary data to a transaction.

```
return;
let myArbitraryData = '1122';
myArbitraryData;
```

### Verify

Verification statements cause the script to fail if their value is not true.

```
let myVar = 5 + 12;
verify myVar == 17;
```

