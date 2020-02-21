# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

import abc
import bisect
import collections
import enum
import itertools
import re
import sys
from typing import Mapping, Sequence, Tuple, Optional, Union, Pattern, Match, cast, MutableMapping, Set, FrozenSet

import attr

from gvm.exceptions import DiagnosticError
from gvm.language.combinators import Combinator, SequenceCombinator, TokenCombinator, ParseletCombinator, \
    flat_combinator, PostfixCombinator
from gvm.language.parser import Parser, ParserError
from gvm.language.syntax import SyntaxNode
from gvm.locations import Location, py_location
from gvm.utils import camel_case_to_lower, cached_property

RE_TOKEN = re.compile('[A-Z][a-zA-Z0-9]*')
RE_PARSELET = re.compile('[a-z][a-z0-9_]*')
PRIORITY_MAX = sys.maxsize
PRIORITY_MIN = 0


@attr.dataclass(hash=True, order=True, eq=True, frozen=True, repr=False)
class SymbolID:
    id: int = attr.attrib(hash=True, order=False, eq=True)
    name: str = attr.attrib(hash=False, order=False, eq=False)
    location: Location = attr.attrib(hash=False, order=False, eq=False, repr=False)

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


@attr.dataclass(frozen=True)
class TokenID(SymbolID):
    description: str = attr.attrib(hash=False, order=False, eq=False, repr=False)


class ParseletKind(enum.IntEnum):
    Pratt = enum.auto()
    Packrat = enum.auto()


@attr.dataclass(frozen=True)
class ParseletID(SymbolID):
    kind: ParseletKind = attr.attrib(hash=False, order=False, eq=False, repr=False)


@attr.dataclass(order=True, frozen=True)
class SyntaxPattern:
    id: TokenID = attr.attrib(order=False, eq=True)
    pattern: Pattern = attr.attrib(order=False, eq=True)
    priority: int = attr.attrib(order=True, eq=True)
    location: Location = attr.attrib(order=False, eq=False)

    def match(self, content: str, start: int) -> Optional[Match[str]]:
        return self.pattern.match(content, start)


@attr.dataclass
class GrammarError(DiagnosticError):
    pass


class Grammar:
    def __init__(self):
        self.__symbols = {}
        self.__tokens = {}
        self.__parselets = {}
        self.__patterns = []
        self.__tables = {}
        self.__trivia = set()
        self.__brackets = set()
        self.__open_brackets = set()
        self.__close_brackets = set()
        self.__bracket_pairs = {}

        # default tokens
        self.add_token('<EOF>', description='end of file', is_implicit=True)
        self.add_token('<ERROR>', description='error token', is_implicit=True)

    @property
    def symbols(self) -> Mapping[str, SymbolID]:
        return self.__symbols

    @property
    def tokens(self) -> Mapping[str, TokenID]:
        return self.__tokens

    @property
    def parselets(self) -> Mapping[str, ParseletID]:
        return self.__parselets

    @property
    def patterns(self) -> Sequence[SyntaxPattern]:
        return self.__patterns

    @property
    def tables(self) -> Mapping[ParseletID, ParseletTable]:
        return self.__tables

    @property
    def trivia(self) -> FrozenSet[TokenID]:
        return cast(FrozenSet[TokenID], self.__trivia)

    @property
    def brackets(self) -> FrozenSet[Tuple[TokenID, TokenID]]:
        return cast(FrozenSet[Tuple[TokenID, TokenID]], self.__brackets)

    @property
    def open_brackets(self) -> FrozenSet[TokenID]:
        return cast(FrozenSet[TokenID], self.__open_brackets)

    @property
    def close_brackets(self) -> FrozenSet[TokenID]:
        return cast(FrozenSet[TokenID], self.__close_brackets)

    @property
    def bracket_pairs(self) -> Mapping[TokenID, TokenID]:
        return self.__bracket_pairs

    def add_token(self, name: str, description: str = None, *, is_implicit: bool = False,
                  location: Location = None) -> TokenID:
        location = location or py_location(2)
        if not is_implicit and not RE_TOKEN.match(name):
            raise GrammarError(location, f'Symbol id for token must be: {RE_TOKEN.pattern}')
        if name in self.__tokens:
            token_id = self.__tokens[name]
            return token_id
        if name in self.__symbols:
            raise GrammarError(location, f'Already registered symbol id: {name}')

        description = description or (name if is_implicit else camel_case_to_lower(name))
        token_id = TokenID(len(self.__symbols) + 1, name, location, description)
        self.__tokens[name] = self.__symbols[name] = token_id
        return token_id

    def add_pattern(self, token_id: TokenID, pattern: str, *, priority: int = PRIORITY_MAX, location: Location = None) \
            -> TokenID:
        location = location or py_location(2)
        bisect.insort_right(self.__patterns, SyntaxPattern(token_id, re.compile(pattern), priority, location))
        return token_id

    def add_implicit(self, pattern: str, *, location: Location = None) -> TokenID:
        location = location or py_location(2)
        token_id = self.add_token(pattern, is_implicit=True, location=location)
        return self.add_pattern(token_id, re.escape(pattern), priority=-len(pattern), location=location)

    def add_trivia(self, token_id: TokenID):
        self.__trivia.add(token_id)

    def add_brackets(self, open_id: TokenID, close_id: TokenID):
        """
        Add open and close brackets.

        Used for indentation scanner

        :param open_id:
        :param close_id:
        :return:
        """
        self.__brackets.add((open_id, close_id))
        self.__open_brackets.add(open_id)
        self.__close_brackets.add(close_id)
        self.__bracket_pairs[open_id] = close_id

    def add_parselet(self, name: str, *, kind: ParseletKind = ParseletKind.Packrat, location: Location = None) \
            -> ParseletID:
        location = location or py_location(2)
        if not RE_PARSELET.match(name):
            raise GrammarError(location, f'Symbol id for parselet must be: {RE_PARSELET.pattern}')
        if name in self.__parselets:
            parser_id = self.__parselets[name]
            if parser_id.kind != kind:
                raise GrammarError(location, f'Can not define parser {parser_id} with different kind')
            return parser_id
        if name in self.__symbols:
            raise GrammarError(location, f'Already registered symbol id: {name}')

        parser_id = ParseletID(len(self.__symbols), name, location, kind)
        self.__parselets[name] = self.__symbols[name] = parser_id
        self.__tables[parser_id] = (PackratTable if kind == ParseletKind.Packrat else PrattTable)(parser_id)
        return parser_id

    def add_parser(self, parser_id: ParseletID, combinator: Union[Combinator, str, SymbolID],
                   *, priority: int = PRIORITY_MAX, location: Location = None) \
            -> AbstractParselet:
        location = location or py_location(2)
        if isinstance(combinator, str):
            from gvm.language.helpers import parse_combinator
            combinator = parse_combinator(self, combinator, location)
        else:
            combinator = flat_combinator(combinator)

        return self.tables[parser_id].add_parser(combinator, priority, location)

    def extend(self, grammar: Grammar, *, location: Location = None):
        """
        Merge current grammar with another
        """
        location = location or py_location(2)
        symbols: MutableMapping[SymbolID, SymbolID] = {}

        # merge tokens
        for token_id in grammar.tokens.values():
            try:
                symbols[token_id] = self.add_token(
                    token_id.name, token_id.description, location=token_id.location, is_implicit=True)
            except GrammarError as ex:
                raise attr.evolve(ex, location=location)

        # merge parsers
        for parser_id in grammar.parselets.values():
            try:
                symbols[parser_id] = self.add_parselet(parser_id.name, kind=parser_id.kind, location=parser_id.location)
            except GrammarError as ex:
                raise attr.evolve(ex, location=location)

        # merge trivia
        for token_id in grammar.trivia:
            self.add_trivia(cast(TokenID, symbols[token_id]))

        # merge brackets
        for open_id, close_id in grammar.brackets:
            self.add_brackets(open_id, close_id)

        # merge token patterns
        for pattern in grammar.patterns:
            if pattern not in self.__patterns:
                token_id: TokenID = cast(TokenID, symbols[pattern.id])
                bisect.insort_right(self.__patterns, SyntaxPattern(
                    token_id, pattern.pattern, pattern.priority, pattern.location
                ))

        # TODO: merge tables

    @classmethod
    def merge(cls, *grammars: Grammar, location: Location = None) -> Grammar:
        """ Merge grammars in one """
        location = location or py_location(2)
        result = cls()
        for grammar in grammars:
            result.extend(grammar, location=location)
        return result


# Result of invocation of parselet: optional syntax node with optional last parser error
ParseletResult = Tuple[Optional[SyntaxNode], Optional[ParserError]]


class ParseletTable(abc.ABC):
    """ This class is abstract base for parselet tables """

    def __init__(self, parser_id: ParseletID) -> None:
        super().__init__()

        self.__parser_id = parser_id

    @property
    def parser_id(self) -> ParseletID:
        return self.__parser_id

    @abc.abstractmethod
    def add_parser(self, combinator: Combinator, priority: int, location: Location) -> AbstractParselet:
        raise NotImplementedError

    @abc.abstractmethod
    def __call__(self, parser: Parser, priority: int) -> ParseletResult:
        raise NotImplementedError


class PrattTable(ParseletTable):
    def __init__(self, parser_id: ParseletID) -> None:
        super().__init__(parser_id)

        self.__prefixes = collections.defaultdict(list)
        self.__postfixes = collections.defaultdict(list)

    @property
    def prefixes(self) -> Mapping[TokenID, Sequence[Parselet]]:
        return self.__prefixes

    @property
    def postfixes(self) -> Mapping[TokenID, Sequence[PostfixParselet]]:
        return self.__postfixes

    @cached_property
    def prefix_tokens(self) -> Set[TokenID]:
        return set(self.prefixes.keys())

    def add_parser(self, combinator: Combinator, priority: int, location: Location) -> AbstractParselet:
        if isinstance(combinator, SequenceCombinator):
            front_combinator = combinator[0]
            if isinstance(front_combinator, TokenCombinator):
                return self.__add_prefix(front_combinator.token_id, combinator, priority, location)

            if isinstance(front_combinator, ParseletCombinator):
                if front_combinator.parser_id == self.parser_id:
                    if len(combinator) > 1:
                        second_combinator = combinator[1]
                        if isinstance(second_combinator, TokenCombinator):
                            return self.__add_postfix(second_combinator.token_id, combinator, priority, location)
                    else:
                        raise GrammarError(location, "Second combinator for Pratt postfix parselet must be token")

        elif isinstance(combinator, TokenCombinator):
            return self.__add_prefix(combinator.token_id, combinator, priority, location)

        raise GrammarError(location, "First combinator for Pratt parselet must be self parser or token")

    def __add_prefix(self, token_id: TokenID, combinator: Combinator, priority: int, location: Location):
        """ Add prefix parser """
        parselet = Parselet(combinator, priority, location)
        bisect.insort_right(self.__prefixes[token_id], parselet)
        self.__dict__.pop('prefix_tokens', None)  # cleanup prefix tokens cache
        return parselet

    def __add_postfix(self, token_id: TokenID, combinator: SequenceCombinator, priority: int, location: Location):
        """ Add postfix parser """
        parselet = PostfixParselet(PostfixCombinator(combinator.combinators), priority, location)
        bisect.insort_right(self.__postfixes[token_id], parselet)
        return parselet

    def __call__(self, parser: Parser, priority: int) -> ParseletResult:
        parselets = self.prefixes.get(parser.current_token.id, ())
        if not parselets:
            raise parser.error(self.prefix_tokens)
        left, error = parser.choice(parselets)

        while True:
            parselets = tuple(itertools.takewhile(
                lambda parselet: priority < parselet.priority, self.postfixes.get(parser.current_token.id, ())
            ))
            if not parselets:
                break

            try:
                left, last_error = parser.choice(parselets, left)
            except ParserError as last_error:
                error = ParserError.merge(error, last_error)
                break
            else:
                error = ParserError.merge(error, last_error)

        return left, error


class PackratTable(ParseletTable):
    def __init__(self, parser_id: ParseletID) -> None:
        super().__init__(parser_id)

        self.__parselets = []

    def add_parser(self, combinator: Combinator, priority: int, location: Location) -> AbstractParselet:
        parselet = Parselet(combinator, priority, location)
        bisect.insort_right(self.__parselets, parselet)
        return parselet

    def __call__(self, parser: Parser, priority: int) -> ParseletResult:
        return parser.choice(self.__parselets)


@attr.dataclass(frozen=True)
class AbstractParselet(abc.ABC):
    combinator: Combinator = attr.attrib(order=False)
    priority: int = attr.attrib(order=True)
    location: Location = attr.attrib(order=False)


@attr.dataclass(frozen=True)
class Parselet(AbstractParselet):
    """ Parselet e.g rule in PEG or prefix rule in Pratt """

    def __call__(self, parser: Parser) -> ParseletResult:
        return self.combinator(parser)


@attr.dataclass(frozen=True)
class PostfixParselet(AbstractParselet):
    """ Postfix parselet, e.g. postfix rule in Pratt """

    def __call__(self, parser: Parser, left: SyntaxNode) -> ParseletResult:
        return self.combinator(parser)
