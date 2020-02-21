# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

import abc
import itertools
from typing import Sequence, overload, Iterator, Optional, Union, Type, Tuple, TYPE_CHECKING, Iterable

import attr

if TYPE_CHECKING:
    from gvm.language.grammar import SymbolID, TokenID, ParseletID
from gvm.language.parser import Parser, ParserError
from gvm.language.syntax import SyntaxNode, SyntaxToken

CombinatorResult = Tuple[Union[SyntaxNode, SyntaxToken, tuple, None], Optional[ParserError]]


@attr.dataclass
class Combinator(abc.ABC):
    @abc.abstractmethod
    def __call__(self, parser: Parser) -> CombinatorResult:
        raise NotImplementedError


@attr.dataclass
class NestedCombinator(Combinator, abc.ABC):
    combinator: Combinator


@attr.dataclass
class TokenCombinator(Combinator):
    """ This combinator consume token from input sequence or failed """
    token_id: TokenID

    def __call__(self, parser: Parser) -> CombinatorResult:
        return parser.consume(self.token_id), None


@attr.dataclass
class ParseletCombinator(Combinator):
    """ This combinator consume result for another parselet or failed """
    parser_id: ParseletID
    priority: Optional[int] = None

    def __call__(self, parser: Parser) -> CombinatorResult:
        return parser.parselet(self.parser_id, self.priority)


@attr.dataclass
class CollectionCombinator(Combinator, Sequence[Combinator], abc.ABC):
    """
    This combinator is used for consume results of combinator's sequence.

    If any of combinator from sequence is failed this combinator also failed
    """
    combinators: Sequence[Combinator]

    @overload
    def __getitem__(self, index: int) -> Combinator: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Combinator]: ...

    def __getitem__(self, index):
        return self.combinators[index]

    def __len__(self) -> int:
        return len(self.combinators)


@attr.dataclass
class SequenceCombinator(CollectionCombinator):
    """
    This combinator is used for consume results of combinator's sequence.

    If any of combinator from sequence is failed this combinator also failed
    """

    def __call__(self, parser: Parser) -> CombinatorResult:
        return sequence(parser, self.combinators)


@attr.dataclass
class PostfixCombinator(SequenceCombinator):
    """
    This combinator is extra version of sequence combinator.

    It's combinator is ignored first nested combinator, e.g. don't make recursive call
    """

    def __call__(self, parser: Parser) -> CombinatorResult:
        return sequence(parser, itertools.islice(self.combinators, 1, None))


@attr.dataclass
class OptionalCombinator(NestedCombinator):
    """
    This combinator consumes nothing if nested combinator is failed.

    Error from nested combinator is propagated to result
    """

    def __call__(self, parser: Parser) -> CombinatorResult:
        try:
            with parser.backtrack():
                return self.combinator(parser)
        except ParserError as error:
            return None, error


@attr.dataclass
class RepeatCombinator(NestedCombinator):
    """
    This combinator is used for repeat nested combinator before it falls
    """

    def __call__(self, parser: Parser) -> CombinatorResult:
        error = None
        while True:
            try:
                with parser.backtrack():
                    _, last_error = self.combinator(parser)
            except ParserError as last_error:
                return None, ParserError.merge(error, last_error)
            else:
                error = ParserError.merge(error, last_error)


def flat_combinator(combinator: Union[Combinator, SymbolID]) -> Combinator:
    from gvm.language.grammar import TokenID, ParseletID
    if isinstance(combinator, TokenID):
        return make_token(combinator)
    if isinstance(combinator, ParseletID):
        return make_parselet(combinator)
    return combinator


def flat_sequence(*combinators: Union[Combinator, SymbolID], kind: Type[CollectionCombinator]) -> Iterator[Combinator]:
    """
    Returns iterator that flatted nested collection combinators plus converted SymbolID to combinator. e.g.

        [[Name, Name], Integer, [[Integer, String], Boolean]]  => [Name, Name, Integer, Integer, String, Boolean]
    """
    assert issubclass(kind, CollectionCombinator)
    for combinator in combinators:
        if isinstance(combinator, kind):
            # noinspection PyUnresolvedReferences
            yield from flat_sequence(*combinator.combinators, kind=kind)
        else:
            yield flat_combinator(combinator)


def make_token(token_id: TokenID) -> TokenCombinator:
    """ Helper for create token combinator """
    from gvm.language.grammar import TokenID
    assert isinstance(token_id, TokenID)
    return TokenCombinator(token_id)


def make_parselet(parser_id: ParseletID, priority: int = None) -> ParseletCombinator:
    """ Helper for create parselet combinator """
    return ParseletCombinator(parser_id, priority)


def make_sequence(*combinators: Union[Combinator, SymbolID]) -> Combinator:
    """
    Helper for create sequence combinator.

    If input sequence of combinators contains only one combinator returns it
    """
    combinators = tuple(flat_sequence(*combinators, kind=SequenceCombinator))
    if len(combinators) == 0:
        raise ValueError("Can not create sequence combinator from empty arguments")
    return combinators[0] if len(combinators) == 1 else SequenceCombinator(combinators)


def make_optional(*combinators: Union[Combinator, SymbolID]) -> Combinator:
    """
    Helper for create optional combinator.
    """
    return OptionalCombinator(make_sequence(*combinators))


def make_repeat(*combinators: Union[Combinator, SymbolID]) -> Combinator:
    return RepeatCombinator(make_sequence(*combinators))


def sequence(parser: Parser, combinators: Iterable[Combinator]) -> CombinatorResult:
    error = None
    for combinator in combinators:
        try:
            _, last_error = combinator(parser)
        except ParserError as last_error:
            raise ParserError.merge(error, last_error)
        else:
            error = ParserError.merge(error, last_error)

    return [], error
