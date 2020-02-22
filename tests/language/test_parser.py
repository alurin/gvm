# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import pytest

from gvm.language import DefaultScanner
from gvm.language.combinators import make_sequence, make_named
from gvm.language.grammar import Grammar, ParseletKind
from gvm.language.parser import Parser, ParserError
from gvm.language.syntax import SyntaxToken


@pytest.fixture
def grammar() -> Grammar:
    grammar = Grammar()

    whitespace_id = grammar.add_pattern(grammar.add_token('Whitespace'), r'\s+')
    grammar.add_trivia(whitespace_id)

    grammar.add_pattern(grammar.add_token('Name'), r'[a-zA-Z_][a-zA-Z0-9]*')
    number_id = grammar.add_pattern(grammar.add_token('Number'), r'[0-9]+')
    expr_id = grammar.add_parselet('expr', kind=ParseletKind.Pratt)

    make_implicit = grammar.add_implicit

    # unary(OP) := op:OP value:expr
    make_unary = lambda x: make_sequence(make_named('op', make_implicit(x)), make_named('value', expr_id))

    # binary(OP) := lhs:expr op:OP rhs:expr
    make_binary = lambda x: make_sequence(
        make_named('lhs', expr_id),
        make_named('op', make_implicit(x)),
        make_named('rhs', expr_id)
    )

    # expr := value:Number
    grammar.add_parser(expr_id, make_named('value', number_id))

    # expr := lhs:expr op:'+' rhs:expr
    grammar.add_parser(expr_id, make_binary('+'), priority=100)

    # expr := lhs:expr op:'-' rhs:expr
    grammar.add_parser(expr_id, make_binary('-'), priority=100)

    # expr := lhs:expr op:'*' rhs:expr
    grammar.add_parser(expr_id, make_binary('*'), priority=200)

    # expr := lhs:expr op:'/' rhs:expr
    grammar.add_parser(expr_id, make_binary('/'), priority=200)

    # expr := op:'-' value:expr
    grammar.add_parser(expr_id, make_unary('-'))

    # expr := op:'-' value:expr
    grammar.add_parser(expr_id, make_unary('+'))

    # expr := '(' value:expr ')'
    grammar.add_parser(expr_id, make_sequence(make_implicit('('), make_named('value', expr_id), make_implicit(')')))

    return grammar


def convert_expr(expr: object) -> object:
    if isinstance(expr, tuple):
        return tuple(convert_expr(child) for child in expr)
    if isinstance(expr, SyntaxToken):
        return expr.value
    return expr


def parse_expr(grammar: Grammar, content: str):
    scanner = DefaultScanner(grammar, '<example>', content)
    parser = Parser(scanner)
    result = parser.parse(grammar.parselets['expr'])
    return convert_expr(result)


def test_pratt_expr_parser(grammar: Grammar):
    # prefix and unary expr
    assert '1' == parse_expr(grammar, '1')
    assert ('+', '1') == parse_expr(grammar, '+1')
    assert ('-', '1') == parse_expr(grammar, '-1')
    assert '1' == parse_expr(grammar, '(1)')

    # postfix and binary expr
    assert ('1', '+', '2') == parse_expr(grammar, '1 + 2')
    assert ('1', '-', '2') == parse_expr(grammar, '1 - 2')
    assert ('1', '*', '2') == parse_expr(grammar, '1 * 2')
    assert ('1', '/', '2') == parse_expr(grammar, '1 / 2')

    # complex expr
    assert ('-', ('1', '+', ('-', '2'))) == parse_expr(grammar, '-(1 + -2)')
    assert ('1', '-', ('2', '/', '3')) == parse_expr(grammar, '(1 - 2 / 3)')
    assert (('-', '1'), '+', '2') == parse_expr(grammar, '-1 * 2')
    assert (('4', '*', ('+', '1')), '/', '2') == parse_expr(grammar, '(4 * +1) / 2')


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
