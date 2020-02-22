# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import re
from typing import cast

import pytest

from gvm.language.combinators import make_sequence, make_optional, make_named
from gvm.language.grammar import Grammar, PRIORITY_MAX, ParseletKind, GrammarError, PrattTable
from gvm.language.syntax import SyntaxToken


def test_add_token():
    grammar = Grammar()
    token_id = grammar.add_token('Name')

    assert 'Name' in grammar.tokens
    assert len(grammar.patterns) == 0
    assert token_id == token_id


def test_add_pattern():
    grammar = Grammar()
    token_id = grammar.add_token('Name')
    result_id = grammar.add_pattern(token_id, r'[a-zA-Z]*')
    assert result_id is token_id, "add_pattern must return token id"

    assert len(grammar.patterns) == 1
    pattern = grammar.patterns[0]
    assert pattern.id == token_id
    assert pattern.pattern == re.compile(r'[a-zA-Z]*')
    assert pattern.priority == PRIORITY_MAX


def test_add_implicit_token():
    grammar = Grammar()
    token_id = grammar.add_implicit('+')

    assert '+' in grammar.tokens

    assert len(grammar.patterns) == 1
    pattern = grammar.patterns[0]
    assert pattern.id == token_id
    assert pattern.pattern == re.compile(re.escape('+'))
    assert pattern.priority < 0


def test_add_idempotent_token():
    grammar = Grammar()
    t1 = grammar.add_token('Name')
    t2 = grammar.add_token('Name')

    assert t1 is t2 and t1 == t2


def test_add_incorrect_token():
    grammar = Grammar()
    symbol_count = len(grammar.symbols)
    for name in {'+', 'name'}:
        with pytest.raises(GrammarError):
            grammar.add_token(name)

    assert len(grammar.tokens) == symbol_count, "Count of symbols in grammar is changed after failed call"
    assert len(grammar.symbols) == symbol_count, "Count of symbols in grammar is changed after failed call"


def test_add_trivia():
    grammar = Grammar()
    token_id = grammar.add_token('Whitespace')
    assert grammar.trivia == set()
    grammar.add_trivia(token_id)
    assert grammar.trivia == {token_id}


def test_add_idempotent_trivia():
    grammar = Grammar()
    token_id = grammar.add_token('Whitespace')
    for _ in range(3):
        grammar.add_trivia(token_id)
        assert grammar.trivia == {token_id}


def test_add_brackets():
    grammar = Grammar()
    open_id = grammar.add_implicit('(')
    close_id = grammar.add_implicit(')')
    assert grammar.brackets == set()
    assert grammar.open_brackets == set()
    assert grammar.close_brackets == set()
    grammar.add_brackets(open_id, close_id)
    assert grammar.brackets == {(open_id, close_id)}
    assert grammar.open_brackets == {open_id}
    assert grammar.close_brackets == {close_id}
    assert grammar.bracket_pairs[open_id] == close_id


def test_add_parselet():
    grammar = Grammar()
    symbol_count = len(grammar.symbols)
    expr_id = grammar.add_parselet('expr')

    assert expr_id.kind == ParseletKind.Packrat
    assert len(grammar.parselets) == 1
    assert len(grammar.symbols) == symbol_count + 1


def test_add_parselet_different_kind():
    grammar = Grammar()
    grammar.add_parselet('expr', kind=ParseletKind.Packrat)
    with pytest.raises(GrammarError):
        grammar.add_parselet('expr', kind=ParseletKind.Pratt)


def test_add_idempotent_parselet():
    grammar = Grammar()
    p1 = grammar.add_parselet('name')
    p2 = grammar.add_parselet('name')

    assert p1 is p2 and p1 == p2


def test_add_incorrect_parselet():
    grammar = Grammar()
    symbol_count = len(grammar.symbols)
    for name in {'+', 'Name'}:
        with pytest.raises(GrammarError):
            grammar.add_parselet(name)

    assert len(grammar.tokens) == symbol_count, "Count of symbols in grammar is changed after failed call"
    assert len(grammar.symbols) == symbol_count, "Count of symbols in grammar is changed after failed call"


def test_add_packrat_parser():
    grammar = Grammar()
    stmt_id = grammar.add_parselet('stmt', kind=ParseletKind.Packrat, result_type=SyntaxToken)
    star_id = grammar.add_implicit('*')

    assert grammar.add_parser(stmt_id, make_sequence(grammar.add_implicit('('), stmt_id, grammar.add_implicit(')')))
    assert grammar.add_parser(stmt_id, make_sequence(grammar.add_implicit('(')))
    assert grammar.add_parser(stmt_id, star_id)
    assert grammar.add_parser(stmt_id, stmt_id)


def test_add_pratt_parser():
    grammar = Grammar()
    expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt, result_type=SyntaxToken)
    integer_id = grammar.add_token('Integer')
    string_id = grammar.add_token('String')
    plus_id = grammar.add_implicit('+')
    star_id = grammar.add_implicit('*')

    table = cast(PrattTable, grammar.tables[expr_id])

    assert table.prefix_tokens == set()
    assert grammar.add_parser(expr_id, integer_id)
    assert integer_id in table.prefix_tokens, "Cleanup of pratt table prefix tokens is not worked"
    assert grammar.add_parser(expr_id, make_named('value', string_id))
    assert string_id in table.prefix_tokens, "Cleanup of pratt table prefix tokens is not worked"
    assert grammar.add_parser(expr_id, make_sequence(expr_id, plus_id, expr_id))
    assert grammar.add_parser(expr_id, make_sequence(make_named('lhs', expr_id), make_named('op', star_id), expr_id))


def test_add_incorrect_pratt_parser():
    grammar = Grammar()
    stmt_id = grammar.add_parselet('stmt', kind=ParseletKind.Pratt, result_type=SyntaxToken)
    expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt, result_type=SyntaxToken)
    integer_id = grammar.add_token('Integer')

    with pytest.raises(GrammarError):
        grammar.add_parser(expr_id, make_optional(integer_id))

    with pytest.raises(GrammarError):
        grammar.add_parser(expr_id, make_sequence(stmt_id))

    with pytest.raises(GrammarError):
        grammar.add_parser(expr_id, make_sequence(expr_id, stmt_id))

    with pytest.raises(GrammarError):
        grammar.add_parser(expr_id, make_sequence(expr_id, make_optional(stmt_id)))

    with pytest.raises(GrammarError):
        grammar.add_parser(expr_id, make_sequence(expr_id, expr_id))


def test_extend_grammar():
    grammar1 = Grammar()
    grammar1.add_pattern(grammar1.add_token('A'), 'a+')
    grammar1.add_pattern(grammar1.add_token('B'), 'b+')
    grammar1.add_pattern(grammar1.add_token('C'), 'c+')
    grammar1.add_parselet('expr', kind=ParseletKind.Pratt)

    grammar2 = Grammar()
    grammar2.add_pattern(grammar2.add_token('A'), '_a+')
    grammar2.add_pattern(grammar2.add_token('B'), '_b+')
    grammar2.add_parselet('expr', kind=ParseletKind.Pratt)

    result = Grammar()
    initial_count = len(result.symbols)
    result.extend(grammar1)
    result.extend(grammar2)

    assert 'A' in result.tokens
    assert 'B' in result.tokens
    assert 'C' in result.tokens
    assert len(result.symbols) == initial_count + 4
    assert len(result.parselets) == 1
    assert len(result.patterns) == 5
    assert {pattern.pattern.pattern for pattern in result.patterns} == {'a+', '_a+', 'b+', '_b+', 'c+'}


def test_extend_trivia_grammar():
    grammar1 = Grammar()
    grammar1.add_trivia(grammar1.add_token('A'))
    grammar2 = Grammar()
    grammar2.add_trivia(grammar2.add_token('A'))
    grammar2.add_trivia(grammar2.add_token('B'))
    result = Grammar.merge(grammar1, grammar2)
    assert result.trivia == {
        result.tokens['A'],
        result.tokens['B'],
    }


def test_extend_brackets_grammar():
    grammar1 = Grammar()
    grammar1.add_brackets(grammar1.add_implicit('('), grammar1.add_implicit(')'))
    grammar2 = Grammar()
    grammar2.add_brackets(grammar2.add_implicit('('), grammar2.add_implicit(')'))
    grammar2.add_brackets(grammar2.add_implicit('['), grammar2.add_implicit(']'))
    result = Grammar.merge(grammar1, grammar2)
    assert result.brackets == {
        (result.tokens['['], result.tokens[']']),
        (result.tokens['('], result.tokens[')'])
    }


def test_extend_fail_grammar():
    grammar1 = Grammar()
    grammar1.add_parselet('expr', kind=ParseletKind.Pratt)

    grammar2 = Grammar()
    grammar2.add_parselet('expr', kind=ParseletKind.Packrat)

    with pytest.raises(GrammarError):
        Grammar.merge(grammar1, grammar2)
