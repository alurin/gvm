# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

from contextlib import contextmanager
from io import StringIO
from typing import Set, Optional, TYPE_CHECKING, MutableMapping, Tuple, Sequence

import attr

from gvm.exceptions import GVMError, dump_source_string
from gvm.language.syntax import SyntaxToken
from gvm.locations import Location
from gvm.writers import Writer, create_writer

if TYPE_CHECKING:
    from gvm.language.scanner import Scanner
    from gvm.language.grammar import TokenID, ParseletID, ParseletResult, Parselet


class Parser:
    """
    This parser is used for parse using Pratt and Packrat algorithm.
    """

    def __init__(self, scanner: Scanner):
        self.grammar = scanner.grammar
        self.scanner = scanner
        self.__tokenizer = iter(self.scanner)
        self.__tokens = []
        self.__position = 0
        self.__memory: MutableMapping[Tuple[int, ParseletID], ParseletResult] = {}

    @property
    def current_token(self) -> SyntaxToken:
        return self.__tokens[self.__position]

    def advance(self) -> SyntaxToken:
        token = self.__tokens[self.__position]
        if token.id != self.scanner.eof_id:
            self.__position += 1
            while self.__position >= len(self.__tokens):
                self.__tokens.append(next(self.__tokenizer))
        return token

    def error(self, indexes: Set[TokenID]) -> ParserError:
        """ Generate exception """
        token_id = self.current_token.id
        return ParserError(self.current_token.location, token_id, indexes)

    def match(self, index: TokenID) -> bool:
        """
        Match current token

        :param index:     Token identifier
        :return: True, if current token is matched passed identifiers
        """
        return self.current_token.id == index

    def consume(self, index: TokenID) -> SyntaxToken:
        """
        Consume current token

        :param index:     Token identifier
        :return: Return consumed token
        :raise Diagnostic if current token is not matched passed identifiers
        """
        if self.current_token.id == index:
            return self.advance()
        raise self.error({index})

    @contextmanager
    def backtrack(self):
        position = self.__position
        try:
            yield
        except ParserError as ex:
            self.__position = position
            raise ex

    def parselet(self, parser_id: ParseletID, priority: int = None) -> ParseletResult:
        """
        Use parselet to consume next tokens and create syntax node.

        This call is cached for given parselet and current position, e.g. using packrat parsing

        :param parser_id:   Parselet identifier
        :param priority:    Initial priority, by default is `PRIORITY_MIN`
        :return:
        """
        priority = priority or 0
        key = (self.__position, parser_id)
        result = self.__memory.get(key, None)
        if not result:
            table = self.grammar.tables[parser_id]
            result = table(self, priority)
            self.__memory[key] = result
        return result

    def choice(self, parselets: Sequence[Parselet], *args) -> ParseletResult:
        error = None
        for parselet in parselets:
            try:
                with self.backtrack():
                    result, last_error = parselet(self, *args)
                    return result, ParserError.merge(error, last_error)
            except ParserError as last_error:
                error = ParserError.merge(error, last_error)

        raise error or ParserConsumeNothingError()

    def parse(self, parser_id: ParseletID):
        """ Parse all tokens from input stream or fail. """
        # first token from scanner
        self.__tokens.append(next(self.__tokenizer))

        # parse start parselet
        result, error = self.parselet(parser_id)

        # required EOF
        try:
            self.consume(self.scanner.eof_id)
        except ParserError as ex:
            raise ParserError.merge(error, ex)
        return result


# noinspection PyShadowingBuiltins
@attr.dataclass
class SyntaxError(GVMError):
    pass


@attr.dataclass
class ParserError(SyntaxError):
    location: Location
    actual_token: TokenID
    expected_tokens: Set[TokenID]

    @staticmethod
    def merge(lhs: Optional[ParserError], rhs: Optional[ParserError]) -> Optional[ParserError]:
        """
        Merge two error at longest position in source text

        :param lhs:
        :param rhs:
        :return:
        """
        if not lhs:
            return rhs
        if not rhs:
            return lhs
        if lhs.location < rhs.location:
            return rhs
        if lhs.location == rhs.location:
            expected_tokens = lhs.expected_tokens | rhs.expected_tokens
            return ParserError(lhs.location, lhs.actual_token, expected_tokens)
        return lhs

    def get_message(self) -> str:
        if len(self.expected_tokens) > 1:
            required_names = []
            for x in self.expected_tokens:
                required_names.append(f'‘{x.description}’')
            return "Required one of {}, but got ‘{}’".format(', '.join(required_names), self.actual_token.description)

        required_name = next(iter(self.expected_tokens), None).description
        return "Required ‘{}’, but got ‘{}’".format(required_name, self.actual_token.description)

    def to_stream(self, stream: Writer, content: str = None):
        dump_source_string(stream, self.location, self.get_message(), content)

    def __str__(self) -> str:
        stream = StringIO()
        self.to_stream(create_writer(stream))
        return stream.getvalue()


class ParserConsumeNothingError(SyntaxError):
    pass
