# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from typing import Optional, Sequence

import pytest

from gvm.language.combinators import flat_combinator, make_sequence, TokenCombinator, ParseletCombinator, flat_sequence, \
    SequenceCombinator, make_named, make_optional, OptionalCombinator, make_repeat, RepeatCombinator, make_token, \
    make_parselet
from gvm.language.grammar import Grammar
from gvm.language.syntax import SyntaxToken, SyntaxNode


def test_flat_combinator():
    grammar = Grammar()
    name_id = grammar.add_token('Name')
    expr_id = grammar.add_parselet('expr')

    # convert token id to token combinator
    comb = flat_combinator(name_id)
    assert isinstance(comb, TokenCombinator)
    assert comb.token_id is name_id

    # convert parselet id to parselet combinator
    comb = flat_combinator(expr_id)
    assert isinstance(comb, ParseletCombinator)
    assert comb.parser_id is expr_id
    assert comb.priority is None

    # don't convert combinator
    comb = TokenCombinator(name_id)
    result = flat_combinator(comb)
    assert comb is result


def test_flat_sequence():
    grammar = Grammar()
    name_id = grammar.add_token('Name')
    expr_id = grammar.add_parselet('expr')

    combinators = tuple(flat_sequence(
        TokenCombinator(name_id),
        ParseletCombinator(expr_id),
        SequenceCombinator((
            TokenCombinator(name_id),
            ParseletCombinator(expr_id),
        )),
        kind=SequenceCombinator
    ))

    assert len(combinators) == 4
    assert isinstance(combinators[0], TokenCombinator)
    assert isinstance(combinators[1], ParseletCombinator)
    assert isinstance(combinators[2], TokenCombinator)
    assert isinstance(combinators[3], ParseletCombinator)


def test_make_token():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    comb = make_token(name_id)
    assert isinstance(comb, TokenCombinator)
    assert comb.token_id == name_id
    assert comb.result_type == SyntaxToken
    assert comb.variables == {}


def test_make_parselet():
    grammar = Grammar()
    name_id = grammar.add_parselet('name')

    comb = make_parselet(name_id)
    assert isinstance(comb, ParseletCombinator)
    assert comb.parser_id == name_id
    assert comb.result_type == SyntaxNode
    assert comb.variables == {}


def test_make_sequence():
    grammar = Grammar()
    name_id = grammar.add_token('Name')
    expr_id = grammar.add_parselet('expr')

    comb = make_sequence(name_id, expr_id)
    assert isinstance(comb, SequenceCombinator)
    assert len(comb) == 2
    assert isinstance(comb[0], TokenCombinator)
    assert isinstance(comb[1], ParseletCombinator)
    assert comb.result_type == SyntaxNode


def test_make_sequence_with_single_element():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    comb = make_sequence(name_id)
    assert isinstance(comb, TokenCombinator)


def test_make_empty_sequence():
    with pytest.raises(ValueError):
        make_sequence()


def test_make_optional():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    comb = make_optional(name_id)
    assert isinstance(comb, OptionalCombinator)
    assert isinstance(comb.combinator, TokenCombinator)
    assert comb.result_type == Optional[SyntaxToken]


def test_make_repeat():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    comb = make_repeat(name_id)
    assert isinstance(comb, RepeatCombinator)
    assert isinstance(comb.combinator, TokenCombinator)
    assert comb.result_type == Sequence[SyntaxToken]


def test_variables():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    # name: Name
    comb = make_named('name', name_id)
    assert 'name' in comb.variables
    assert comb.variables['name'] == SyntaxToken

    # names: Name names: Name
    comb = make_sequence(make_named('names', name_id), make_named('names', name_id))
    assert 'names' in comb.variables
    assert comb.variables['names'] == Sequence[SyntaxToken]

    # [ name: Name ]
    comb = make_optional(make_named('name', name_id))
    assert 'name' in comb.variables
    assert comb.variables['name'] == Optional[SyntaxToken]

    # { name: Name }
    comb = make_repeat(make_named('names', name_id))
    assert comb.variables['names'] == Sequence[SyntaxToken]

    # names: Name { names: Name }
    comb = make_sequence(make_named('names', name_id), make_repeat(make_named('names', name_id)))
    assert 'names' in comb.variables
    assert comb.variables['names'] == Sequence[SyntaxToken]

    # names: { Name }
    comb = make_named('names', make_repeat(name_id))
    assert 'names' in comb.variables
    assert comb.variables['names'] == Sequence[SyntaxToken]
