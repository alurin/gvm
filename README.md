GVM
===

This project contains my experimental project with extendable 
syntax grammar.

Brief
-----

Core of project is syntax grammar (`gvm.language.Grammar`).

General elements of it's:

- `gvm.language.TokenID`  - token identifier, e.g. terminal symbol
- `gvm.language.ParseletID` - parselet identifier, e.g. non-terminal symbol

Grammar also contains patterns for tokenize from source text to 
syntax tokens (`gvm.language.SyntaxToken`).


Example of grammar
------------------

This version is used explicit definition of grammar (e.g. parselet definition is imperative)

```python
from gvm.language.combinators import make_sequence
from gvm.language.grammar import Grammar, ParseletKind

grammar = Grammar()

grammar.add_pattern(grammar.add_token('Whitespace'), r'\s+')
grammar.add_pattern(grammar.add_token('Name'), r'[a-zA-Z_][a-zA-Z0-9]*')
number_id = grammar.add_pattern(grammar.add_token('Number'), r'[0-9]+')
expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt)
grammar.add_trivia(grammar.tokens['Whitespace'])

implicit = grammar.add_implicit

# expr := Number
grammar.add_parser(expr_id, number_id)
# expr := expr '+' expr
grammar.add_parser(expr_id, make_sequence(expr_id, implicit('+'), expr_id), priority=100)
# expr := expr '-' expr
grammar.add_parser(expr_id, make_sequence(expr_id, implicit('-'), expr_id), priority=100)
# expr := expr '*' expr
grammar.add_parser(expr_id, make_sequence(expr_id, implicit('*'), expr_id), priority=200)
# expr := expr '/' expr
grammar.add_parser(expr_id, make_sequence(expr_id, implicit('/'), expr_id), priority=200)
# expr := '-' expr
grammar.add_parser(expr_id, make_sequence(implicit('-'), expr_id))
# expr := '-' expr
grammar.add_parser(expr_id, make_sequence(implicit('+'), expr_id))
# expr := '(' expr ')'
grammar.add_parser(expr_id, make_sequence(implicit('('), expr_id, implicit(')')))
```

License
-------

This project is published by MIT license. For full test of license view [LICENSE.md](LICENSE.md)

Installation
------------

This project is used Python 3.7 as minimum version.

Also install `attrs` and `pytest` (for tests)

Testing
-------

Run `pytest` 
