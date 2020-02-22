# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from gvm.language import Grammar
from gvm.language.combinators import TokenCombinator, ParseletCombinator, OptionalCombinator, RepeatCombinator
from gvm.language.helpers import parse_combinator


def test_parse_token_combinator():
    # comb := NAME
    grammar = Grammar()
    token_id = grammar.add_token('Name')
    result = parse_combinator(grammar, 'Name')
    assert isinstance(result, TokenCombinator)
    assert result.token_id == token_id


def test_parse_parselet_combinator():
    # comb := NAME
    grammar = Grammar()
    parser_id = grammar.add_parselet('name')
    result = parse_combinator(grammar, 'name')
    assert isinstance(result, ParseletCombinator)
    assert result.parser_id == parser_id


def test_parse_existed_implicit_combinator():
    # comb := STRING
    grammar = Grammar()
    token_id = grammar.add_implicit('(')
    result = parse_combinator(grammar, '"("')
    assert isinstance(result, TokenCombinator)
    assert result.token_id == token_id


def test_parse_non_existed_implicit_combinator():
    # comb := STRING
    grammar = Grammar()
    result = parse_combinator(grammar, '"("')
    assert '(' in grammar.tokens
    assert isinstance(result, TokenCombinator)
    assert result.token_id == grammar.tokens['(']
    assert result.token_id == grammar.add_implicit('(')


def test_parse_optional_combinator():
    # comb := '[' seq ']'
    grammar = Grammar()
    token_id = grammar.add_token('Name')
    result = parse_combinator(grammar, '[ Name ]')
    assert isinstance(result, OptionalCombinator)
    assert isinstance(result.combinator, TokenCombinator)
    assert result.combinator.token_id == token_id


def test_parse_repeat_combinator():
    # comb := '{' seq '}'
    grammar = Grammar()
    token_id = grammar.add_token('Name')
    result = parse_combinator(grammar, '{ Name }')
    assert isinstance(result, RepeatCombinator)
    assert isinstance(result.combinator, TokenCombinator)
    assert result.combinator.token_id == token_id
