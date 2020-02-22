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
from typing import Mapping, Sequence, Tuple, Optional, Union, Pattern, Match, cast, MutableMapping, Set, FrozenSet, \
    Type

import attr

from gvm.exceptions import DiagnosticError
from gvm.language.actions import ActionGenerator, make_return_result, Action
from gvm.language.combinators import Combinator, SequenceCombinator, TokenCombinator, ParseletCombinator, \
    flat_combinator, PostfixCombinator, NamedCombinator
from gvm.language.parser import Parser, ParserError
from gvm.language.syntax import SyntaxNode
from gvm.locations import Location, py_location
from gvm.typing import make_default_mutable_value, is_sequence_type, is_subclass
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
    is_implicit: bool = attr.attrib(hash=False, order=False, eq=False, repr=False)


class ParseletKind(enum.IntEnum):
    Pratt = enum.auto()
    Packrat = enum.auto()


@attr.dataclass(frozen=True)
class ParseletID(SymbolID):
    kind: ParseletKind = attr.attrib(hash=False, order=False, eq=False, repr=False)
    result_type: Type = attr.attrib(hash=False, order=False, eq=False, repr=False)


@attr.dataclass(order=True, frozen=True, repr=False)
class SyntaxPattern:
    token_id: TokenID = attr.attrib(order=False, eq=True)
    pattern: Pattern = attr.attrib(order=False, eq=True)
    priority: int = attr.attrib(order=True, eq=True)
    location: Location = attr.attrib(order=False, eq=False)
    is_implicit: bool = attr.attrib(order=False, eq=False)

    def match(self, content: str, start: int) -> Optional[Match[str]]:
        return self.pattern.match(content, start)

    def __str__(self) -> str:
        from gvm.language.printer import dump_pattern
        return dump_pattern.to_string(self)


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
        token_id = TokenID(len(self.__symbols) + 1, name, location, description, is_implicit)
        self.__tokens[name] = self.__symbols[name] = token_id
        return token_id

    def add_pattern(self, token_id: TokenID, pattern: str, *, priority: int = PRIORITY_MAX, location: Location = None,
                    is_implicit: bool = False) -> TokenID:
        location = location or py_location(2)
        bisect.insort_right(
            self.__patterns, SyntaxPattern(token_id, re.compile(pattern), priority, location, is_implicit))
        return token_id

    def add_implicit(self, pattern: str, *, location: Location = None) -> TokenID:
        location = location or py_location(2)
        token_id = self.add_token(pattern, is_implicit=True, location=location)
        return self.add_pattern(token_id, re.escape(pattern), priority=-len(pattern), location=location,
                                is_implicit=True)

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

    def add_parselet(self, name: str, *, result_type: Type = None, kind: ParseletKind = ParseletKind.Packrat,
                     location: Location = None) -> ParseletID:
        result_type = result_type or SyntaxNode
        location = location or py_location(2)
        if not RE_PARSELET.match(name):
            raise GrammarError(location, f'Symbol id for parselet must be: {RE_PARSELET.pattern}')
        if name in self.__parselets:
            parser_id = self.__parselets[name]
            if parser_id.kind != kind:
                raise GrammarError(location, f'Can not define parser {parser_id} with different kind')
            if parser_id.result_type != result_type:
                raise GrammarError(location, f'Can not define parser {parser_id} with different return type')
            return parser_id
        if name in self.__symbols:
            raise GrammarError(location, f'Already registered symbol id: {name}')

        parser_id = ParseletID(len(self.__symbols), name, location, kind, result_type)
        self.__parselets[name] = self.__symbols[name] = parser_id
        self.__tables[parser_id] = (PackratTable if kind == ParseletKind.Packrat else PrattTable)(parser_id)
        return parser_id

    def add_parser(self, parser_id: Union[str, ParseletID], combinator: Union[Combinator, str, SymbolID],
                   generator: ActionGenerator = None, *, priority: int = PRIORITY_MAX, location: Location = None) \
            -> ParseletID:
        location = location or py_location(2)
        # convert input combinator to instance of Combinator
        if isinstance(combinator, str):
            from gvm.language.helpers import make_combinator
            combinator = make_combinator(self, combinator, location)
        else:
            combinator = flat_combinator(combinator)

        # convert action to combinator action
        generator = generator or make_return_result()
        action = generator(combinator)

        # check parser type
        if isinstance(parser_id, str):
            parser_id = self.add_parselet(parser_id, location=location, result_type=action.result_type)
        else:
            # check result of action with ret
            if not is_subclass(action.result_type, parser_id.result_type):
                raise GrammarError(
                    location,
                    f'Can not add parser to parselet because return types is different: '
                    f'{action.result_type} and {parser_id.result_type}'
                )

        # add parser tot table
        self.tables[parser_id].add_parser(combinator, action, priority, location)
        return parser_id

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
                    token_id.name, token_id.description, location=token_id.location, is_implicit=token_id.is_implicit)
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
                token_id: TokenID = cast(TokenID, symbols[pattern.token_id])
                bisect.insort_right(self.__patterns, SyntaxPattern(
                    token_id, pattern.pattern, pattern.priority, pattern.location, pattern.is_implicit
                ))

        # merge parser tables
        for table in grammar.tables.values():
            parser_id = cast(ParseletID, symbols[table.parser_id])
            new_table: ParseletTable = self.tables[parser_id]
            for parselet in table.parselets:
                combinator = parselet.combinator.clone(symbols)
                new_table.add_parser(combinator, parselet.action, parselet.priority, parselet.location)

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

    @property
    @abc.abstractmethod
    def parselets(self) -> Sequence[Parselet]:
        raise NotImplementedError

    @abc.abstractmethod
    def add_parser(self, combinator: Combinator, action: Action, priority: int, location: Location) -> Parselet:
        raise NotImplementedError

    @abc.abstractmethod
    def __call__(self, parser: Parser, priority: int) -> ParseletResult:
        raise NotImplementedError


class PrattTable(ParseletTable):
    def __init__(self, parser_id: ParseletID) -> None:
        super().__init__(parser_id)

        self.__prefixes = collections.defaultdict(list)
        self.__postfixes = collections.defaultdict(list)
        self.__parselets = []

    @property
    def parselets(self) -> Sequence[Parselet]:
        return self.__parselets

    @property
    def prefixes(self) -> Mapping[TokenID, Sequence[PrefixParselet]]:
        return self.__prefixes

    @property
    def postfixes(self) -> Mapping[TokenID, Sequence[PostfixParselet]]:
        return self.__postfixes

    @cached_property
    def prefix_tokens(self) -> Set[TokenID]:
        return set(self.prefixes.keys())

    def add_parser(self, combinator: Combinator, action: Action, priority: int, location: Location) -> Parselet:
        if isinstance(combinator, SequenceCombinator):
            front_combinator = combinator[0]
            if isinstance(front_combinator, NamedCombinator):
                front_combinator = front_combinator.combinator
            if isinstance(front_combinator, TokenCombinator):
                return self.__add_prefix(front_combinator.token_id, combinator, action, priority, location)

            if isinstance(front_combinator, ParseletCombinator):
                if front_combinator.parser_id == self.parser_id:
                    if len(combinator) > 1:
                        second_combinator = combinator[1]
                        if isinstance(second_combinator, NamedCombinator):
                            second_combinator = second_combinator.combinator
                        if isinstance(second_combinator, TokenCombinator):
                            return self.__add_postfix(
                                second_combinator.token_id, combinator, action, priority, location)
                    else:
                        raise GrammarError(location, "Second combinator for Pratt postfix parselet must be token")
        else:
            front_combinator = combinator
            if isinstance(front_combinator, NamedCombinator):
                front_combinator = front_combinator.combinator
            if isinstance(front_combinator, TokenCombinator):
                return self.__add_prefix(front_combinator.token_id, combinator, action, priority, location)

        raise GrammarError(location, "First combinator for Pratt parselet must be self parser or token")

    def __add_prefix(self, token_id: TokenID, combinator: Combinator, action: Action, priority: int,
                     location: Location):
        """ Add prefix parser """
        parselet = PrefixParselet(self.parser_id, combinator, action, priority, location)
        bisect.insort_right(self.__prefixes[token_id], parselet)
        bisect.insort_right(self.__parselets, parselet)
        self.__dict__.pop('prefix_tokens', None)  # cleanup prefix tokens cache
        return parselet

    def __add_postfix(self, token_id: TokenID, combinator: SequenceCombinator, action: Action, priority: int,
                      location: Location):
        """ Add postfix parser """
        parselet = PostfixParselet(self.parser_id, PostfixCombinator(combinator.combinators), action, priority,
                                   location)
        bisect.insort_right(self.__postfixes[token_id], parselet)
        bisect.insort_right(self.__parselets, parselet)
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

    @property
    def parselets(self) -> Sequence[Parselet]:
        return self.__parselets

    def add_parser(self, combinator: Combinator, action: Action, priority: int, location: Location) -> Parselet:
        parselet = PrefixParselet(self.parser_id, combinator, action, priority, location)
        bisect.insort_right(self.__parselets, parselet)
        return parselet

    def __call__(self, parser: Parser, priority: int) -> ParseletResult:
        return parser.choice(self.__parselets)


@attr.dataclass(frozen=True, repr=False, order=False, eq=False)
class Parselet(abc.ABC):
    parser_id: ParseletID
    combinator: Combinator
    action: Action
    priority: int
    location: Location

    @property
    def variables(self) -> Mapping[str, Type]:
        return self.combinator.variables

    @property
    def result_type(self) -> Type:
        return self.action.result_type

    def merge_namespace(self, namespace: Mapping[str, object]) -> Mapping[str, object]:
        result = {}
        for name, typ in self.variables.items():
            if name not in namespace:
                result[name] = make_default_mutable_value(typ)
            else:
                # noinspection PyTypeChecker
                result[name] = tuple(namespace[name]) if is_sequence_type(typ) else namespace[name]
        return result

    @abc.abstractmethod
    def __call__(self, parser: Parser) -> ParseletResult:
        raise NotImplementedError

    def __lt__(self, other: Parselet):
        if not isinstance(other, Parselet):
            raise TypeError(
                f"'<' not supported between instances of '{type(self).__name__}' and '{type(other).__name__}'")
        return self.priority < other.priority

    def __gt__(self, other: Parselet):
        if not isinstance(other, Parselet):
            raise TypeError(
                f"'>' not supported between instances of '{type(self).__name__}' and '{type(other).__name__}'")
        return self.priority > other.priority

    def __str__(self) -> str:
        from gvm.language.printer import dump_parselet
        return dump_parselet.to_string(self)

    def __repr__(self) -> str:
        class_name = type(self).__name__
        return f'<{class_name}: {self}>'


@attr.dataclass(frozen=True, order=False, eq=False)
class PrefixParselet(Parselet):
    """ Parselet e.g rule in PEG or prefix rule in Pratt """

    def __call__(self, parser: Parser) -> ParseletResult:
        result, namespace, error = self.combinator(parser, self)
        result = self.action(result, self.merge_namespace(namespace))
        return result, error


@attr.dataclass(frozen=True, order=False, eq=False)
class PostfixParselet(Parselet):
    """ Postfix parselet, e.g. postfix rule in Pratt """

    def __call__(self, parser: Parser, left: SyntaxNode = None) -> ParseletResult:
        result, namespace, error = cast(PostfixCombinator, self.combinator).fixme(parser, self, left)
        result = self.action(result, self.merge_namespace(namespace))
        return result, error
