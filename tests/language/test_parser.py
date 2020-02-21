# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import pytest

from gvm.language import DefaultScanner
from gvm.language.combinators import make_sequence
from gvm.language.grammar import Grammar, ParseletKind
from gvm.language.parser import Parser, ParserError


@pytest.fixture
def grammar() -> Grammar:
    grammar = Grammar()

    whitespace_id = grammar.add_pattern(grammar.add_token('Whitespace'), r'\s+')
    grammar.add_trivia(whitespace_id)

    grammar.add_pattern(grammar.add_token('Name'), r'[a-zA-Z_][a-zA-Z0-9]*')
    number_id = grammar.add_pattern(grammar.add_token('Number'), r'[0-9]+')
    expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt)

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

    return grammar


def parse_expr(grammar: Grammar, content: str):
    scanner = DefaultScanner(grammar, '<example>', content)
    parser = Parser(scanner)
    return parser.parse(grammar.parselets['expr'])


def test_pratt_expr_parser(grammar: Grammar):
    # prefix and unary expr
    parse_expr(grammar, '1')
    parse_expr(grammar, '+1')
    parse_expr(grammar, '-1')
    parse_expr(grammar, '(1)')

    # postfix and binary expr
    parse_expr(grammar, '1 + 2')
    parse_expr(grammar, '1 - 2')
    parse_expr(grammar, '1 * 2')
    parse_expr(grammar, '1 / 2')

    # complex expr
    parse_expr(grammar, '-(1 + -2)')
    parse_expr(grammar, '(1 - 2 / 3)')
    parse_expr(grammar, '-1 * 2')
    parse_expr(grammar, '(4 * +1) / 2')


def test_expr_parse_invalid_name(grammar: Grammar):
    with pytest.raises(ParserError) as exc_info:
        parse_expr(grammar, 'a')
    ex = exc_info.value
    assert ex.actual_token == grammar.tokens['Name']
    assert ex.expected_tokens == {
        grammar.tokens['('],
        grammar.tokens['+'],
        grammar.tokens['-'],
        grammar.tokens['Number'],
    }
