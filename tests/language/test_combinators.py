# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import pytest

from gvm.language.combinators import flat_combinator, make_sequence, TokenCombinator, ParseletCombinator, flat_sequence, \
    SequenceCombinator
from gvm.language.grammar import Grammar


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


def test_make_sequence():
    grammar = Grammar()
    name_id = grammar.add_token('Name')
    expr_id = grammar.add_parselet('expr')

    comb = make_sequence(name_id, expr_id)
    assert isinstance(comb, SequenceCombinator)
    assert len(comb) == 2
    assert isinstance(comb[0], TokenCombinator)
    assert isinstance(comb[1], ParseletCombinator)


def test_make_sequence_with_single_element():
    grammar = Grammar()
    name_id = grammar.add_token('Name')

    comb = make_sequence(name_id)
    assert isinstance(comb, TokenCombinator)


def test_make_empty_sequence():
    with pytest.raises(ValueError):
        make_sequence()
