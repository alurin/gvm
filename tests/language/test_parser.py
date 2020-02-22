# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import pytest

from gvm.language import DefaultScanner
from gvm.language.actions import make_call, make_return_variable
from gvm.language.grammar import Grammar, ParseletKind
from gvm.language.parser import Parser, ParserError


@pytest.fixture
def grammar() -> Grammar:
    grammar = Grammar()

    whitespace_id = grammar.add_pattern(grammar.add_token('Whitespace'), r'\s+')
    grammar.add_trivia(whitespace_id)

    grammar.add_pattern(grammar.add_token('Name'), r'[a-zA-Z_][a-zA-Z0-9]*')
    grammar.add_pattern(grammar.add_token('Number'), r'[0-9]+')

    make_implicit = grammar.add_implicit

    expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt, result_type=object)

    # expr := value:Number
    grammar.add_parser(expr_id, "value:Number", make_call(lambda value: value.value, object))

    # expr := lhs:expr op:'+' rhs:expr
    grammar.add_parser(
        expr_id, 'lhs:expr "**" rhs:expr <899>', make_call(lambda lhs, rhs: (lhs, '**', rhs), object), priority=900)

    # expr := lhs:expr op:'+' rhs:expr
    grammar.add_parser(
        expr_id, 'lhs:expr "+" rhs:expr <600>', make_call(lambda lhs, rhs: (lhs, '+', rhs), object), priority=600)

    # expr := lhs:expr op:'-' rhs:expr
    grammar.add_parser(
        expr_id, 'lhs:expr "-" rhs:expr <600>', make_call(lambda lhs, rhs: (lhs, '-', rhs), object), priority=600)

    # expr := lhs:expr op:'*' rhs:expr
    grammar.add_parser(
        expr_id, 'lhs:expr "*" rhs:expr <700>', make_call(lambda lhs, rhs: (lhs, '*', rhs), object), priority=700)

    # expr := lhs:expr op:'/' rhs:expr
    grammar.add_parser(
        expr_id, 'lhs:expr "/" rhs:expr <700>', make_call(lambda lhs, rhs: (lhs, '/', rhs), object), priority=700)

    # expr := op:'-' value:expr
    grammar.add_parser(expr_id, '"-" value:expr <800>', make_call(lambda value: ('-', value), object))

    # expr := op:'-' value:expr
    grammar.add_parser(expr_id, '"+" value:expr <800>', make_call(lambda value: ('+', value), object))

    # expr := '(' value:expr ')'
    grammar.add_parser(expr_id, '"(" value:expr ")"', make_return_variable('value'))

    return grammar


def parse_expr(grammar: Grammar, content: str):
    scanner = DefaultScanner(grammar, '<example>', content)
    parser = Parser(scanner)
    result = parser.parse(grammar.parselets['expr'])
    return result


def test_pratt_expr_parser(grammar: Grammar):
    # prefix and unary expr
    assert parse_expr(grammar, '1') == '1'
    assert parse_expr(grammar, '+1') == ('+', '1')
    assert parse_expr(grammar, '-1') == ('-', '1')
    assert parse_expr(grammar, '(1)') == '1'

    # postfix and binary expr
    assert parse_expr(grammar, '1 + 2') == ('1', '+', '2')
    assert parse_expr(grammar, '1 - 2') == ('1', '-', '2')
    assert parse_expr(grammar, '1 * 2') == ('1', '*', '2')
    assert parse_expr(grammar, '1 / 2') == ('1', '/', '2')

    # priority parsers, e.g. associativity and precedence
    assert parse_expr(grammar, '1 + 2 + 3') == (('1', '+', '2'), '+', '3')
    assert parse_expr(grammar, '1 * 2 * 3') == (('1', '*', '2'), '*', '3')
    assert parse_expr(grammar, '1 ** 2 ** 3') == ('1', '**', ('2', '**', '3'))

    assert parse_expr(grammar, '1 + 2 * 3') == ('1', '+', ('2', '*', '3'))
    assert parse_expr(grammar, '1 * 2 + 3') == (('1', '*', '2'), '+', '3')

    # complex expr
    assert parse_expr(grammar, '-(1 + -2)') == ('-', ('1', '+', ('-', '2')))
    assert parse_expr(grammar, '(1 - 2 / 3)') == ('1', '-', ('2', '/', '3'))
    assert parse_expr(grammar, '-1 * 2') == (('-', '1'), '*', '2')
    assert parse_expr(grammar, '(4 * +1) / 2') == (('4', '*', ('+', '1')), '/', '2')


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
