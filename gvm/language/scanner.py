# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

import collections
from typing import Iterator, Optional

from gvm.language.grammar import Grammar, TokenID
from gvm.language.syntax import SyntaxToken
from gvm.locations import Location


class Scanner:
    """
    This class is implemented tokenizer, that tokenize input stream to tokens.

    This tokenizer returns all tokens from source text, e.g. trivia, errors and e.t.c
    """

    eof_id: TokenID
    error_id: TokenID

    def __init__(self, grammar: Grammar, filename: str, content: str):
        self.grammar = grammar
        self.position = 0
        self.buffer = content
        self.length = len(self.buffer)
        self.location = Location(filename)
        self.eof_id = grammar.tokens['<EOF>']
        self.error_id = grammar.tokens['<ERROR>']

    def tokenize(self) -> Iterator[SyntaxToken]:
        while self.position < self.length:
            token = self.__match()
            if token:
                yield token

        yield SyntaxToken(self.eof_id, "", self.location)

    def __match(self) -> Optional[SyntaxToken]:
        self.location.columns(1)
        self.location = self.location.step()

        # match patterns
        results = ((pattern.id, pattern.match(self.buffer, self.position)) for pattern in self.grammar.patterns)
        results = tuple((token_id, match) for token_id, match in results if match)
        if results:
            max_position = max(match.end() for _, match in results)
            token_id, match = next((token_id, match) for token_id, match in results if match.end() == max_position)
            position = match.end()
            value = self.buffer[self.position:position]
        else:
            # match operators
            value = self.buffer[self.position]
            token_id = self.error_id
            self.position += 1

        self.position += len(value)
        location = self.__consume_location(value)
        return SyntaxToken(token_id, value, location)

    def __consume_location(self, value):
        for c in value[:-1]:
            if c == '\n':
                self.location = self.location.lines(1)
            elif len(value) > 1:
                self.location = self.location.columns(1)
        location = self.location
        if value[-1] == '\n':
            self.location = self.location.lines(1)
        else:
            self.location = self.location.columns(1)
        return location

    def __iter__(self):
        return self.tokenize()


class DefaultScanner(Scanner):
    """ This class is implemented tokenizer, that skipped trivia tokens from output tokens """

    def tokenize(self) -> Iterator[SyntaxToken]:
        for token in super().tokenize():
            if token.id not in self.grammar.trivia:
                yield token


class IndentationScanner(Scanner):
    """
    This class is implemented tokenizer, that tracks indentations in source text (offset rule) and
    appended `indent` and `dedent` tokens to output tokens. Also skipped trivia tokens
    """

    def __init__(self, grammar: Grammar, filename: str, content: str):
        super().__init__(grammar, filename, content)

        self.newline_id = grammar.add_token('NewLine')
        self.whitespace_id = grammar.add_token('Whitespace')
        self.indent_id = grammar.add_token('Indent')
        self.dedent_id = grammar.add_token('Dedend')

    def tokenize(self) -> Iterator[SyntaxToken]:
        indentations = collections.deque([0])
        is_new = True  # new line
        whitespace = None
        level = 0  # disable indentation

        for token in super().tokenize():
            # new line
            if token.id == self.newline_id:
                if level:
                    continue

                if not is_new:
                    yield token

                is_new = True
                continue

            elif token.id == self.whitespace_id:
                if is_new:
                    whitespace = token
                continue

            elif token.id == self.eof_id:
                location = Location(token.location.filename, token.location.end, token.location.end)

                if not is_new:
                    yield SyntaxToken(self.newline_id, '', location)

                while indentations[-1] > 0:
                    yield SyntaxToken(self.dedent_id, '', location)
                    indentations.pop()

                yield token
                continue

            elif token.id in self.grammar.trivia:
                continue

            if is_new:
                if whitespace:
                    indent = len(whitespace.value)
                    location = whitespace.location
                    whitespace = None
                else:
                    indent = 0
                    location = Location(token.location.filename, token.location.begin, token.location.begin)

                if indentations[-1] < indent:
                    yield SyntaxToken(self.indent_id, '', location)
                    indentations.append(indent)
                else:
                    while indentations[-1] > indent:
                        yield SyntaxToken(self.indent_id, '', location)
                        indentations.pop()

            is_new = False
            if token.id in self.grammar.open_brackets:
                level += 1
            elif token.id in self.grammar.close_brackets:
                level -= 1

            yield token
