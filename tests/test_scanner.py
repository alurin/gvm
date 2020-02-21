# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from typing import Sequence, Tuple

import pytest

from gvm.language.grammar import Grammar, TokenID
from gvm.language.scanner import Scanner, DefaultScanner


def tokenize_to_tuple(scanner: Scanner) -> Sequence[Tuple[TokenID, str]]:
    return tuple((token.id, token.value) for token in scanner)


@pytest.fixture
def grammar() -> Grammar:
    grammar = Grammar()

    whitespace_id = grammar.add_pattern(grammar.add_token('Whitespace'), r'\s+')
    grammar.add_trivia(whitespace_id)
    grammar.add_pattern(grammar.add_token('Number'), r'[0-9]+')
    grammar.add_pattern(grammar.add_token('Name'), r'[a-zA-Z_][a-zA-Z0-9]+')
    grammar.add_implicit("for")
    grammar.add_implicit("while")
    grammar.add_implicit("+")
    grammar.add_implicit("-")

    return grammar


def test_tokenize(grammar: Grammar):
    whitespace_id = grammar.tokens['Whitespace']
    number_id = grammar.tokens['Number']
    eof_id = grammar.tokens['<EOF>']

    assert tokenize_to_tuple(Scanner(grammar, "<example>", "12 13 14")) == (
        (number_id, "12"),
        (whitespace_id, " "),
        (number_id, "13"),
        (whitespace_id, " "),
        (number_id, "14"),
        (eof_id, ""),
    )


def test_tokenize_without_trivia(grammar: Grammar):
    number_id = grammar.tokens['Number']
    eof_id = grammar.tokens['<EOF>']

    tokens = tokenize_to_tuple(DefaultScanner(grammar, "<example>", "12 13 14"))
    assert tokens == (
        (number_id, "12"),
        (number_id, "13"),
        (number_id, "14"),
        (eof_id, ""),
    )


def test_tokenize_error(grammar: Grammar):
    error_id = grammar.tokens['<ERROR>']
    eof_id = grammar.tokens['<EOF>']

    assert tokenize_to_tuple(Scanner(grammar, "<example>", "?")) == (
        (error_id, "?"),
        (eof_id, ""),
    )


def test_tokenize_names(grammar: Grammar):
    eof_id = grammar.tokens['<EOF>']
    name_id = grammar.tokens['Name']
    for_id = grammar.tokens['for']
    while_id = grammar.tokens['while']

    assert tokenize_to_tuple(Scanner(grammar, "<example>", "name")) == ((name_id, "name"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "for")) == ((for_id, "for"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "fore")) == ((name_id, "fore"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "fo")) == ((name_id, "fo"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "while")) == ((while_id, "while"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "whiles")) == ((name_id, "whiles"), (eof_id, ""))
    assert tokenize_to_tuple(Scanner(grammar, "<example>", "whil")) == ((name_id, "whil"), (eof_id, ""))

# TODO: Add tests for indention scanner
