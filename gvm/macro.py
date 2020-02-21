# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from gvm.core import create_core_grammar
from gvm.language.combinators import make_sequence, make_repeat
from gvm.language.grammar import Grammar


def create_combinator_grammar() -> Grammar:
    """
    Create grammar for parse combinator definition

    P.S. This grammar is used for bootstrap process of initial grammar, e.g. definition of combinators in grammar
    """
    grammar = Grammar()
    grammar.extend(create_core_grammar())

    # tokens
    name_id = grammar.tokens['Name']
    string_id = grammar.tokens['String']
    dot_id = grammar.add_implicit('.')
    square_left_id = grammar.tokens['[']
    square_right_id = grammar.tokens[']']
    curly_left_id = grammar.tokens['{']
    curly_right_id = grammar.tokens['}']

    # parse combinator definition
    comb_id = grammar.add_parselet('combinator')
    seq_id = grammar.add_parselet('combinator_sequence')

    # combinator := Name { "." Name }                   ; reference to parselet or token
    grammar.add_parser(comb_id, make_sequence(name_id, make_repeat(dot_id, name_id)))

    # combinator := String                              ; reference to implicit token
    grammar.add_parser(comb_id, string_id)

    # combinator := '[' combinator_sequence ']'         ; optional combinator
    grammar.add_parser(comb_id, make_sequence(square_left_id, seq_id, square_right_id))

    # combinator := '{' combinator_sequence '}'         ; repeat combinator
    grammar.add_parser(comb_id, make_sequence(curly_left_id, seq_id, curly_right_id))

    # combinator_sequence := combinator { combinator }  ; sequence combinator
    grammar.add_parser(seq_id, make_sequence(comb_id, make_repeat(comb_id)))

    return grammar
