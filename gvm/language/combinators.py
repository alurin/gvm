# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

import abc
import itertools
from typing import Sequence, overload, Iterator, Optional, Union, Type, Tuple, TYPE_CHECKING, Iterable, Mapping

import attr

from gvm.typing import merge_sequence_type, make_optional_type, make_sequence_type, is_sequence_type
from gvm.utils import cached_property

if TYPE_CHECKING:
    from gvm.language.grammar import SymbolID, TokenID, ParseletID, AbstractParselet
from gvm.language.parser import Parser, ParserError
from gvm.language.syntax import SyntaxToken

CombinatorResult = Tuple[object, Mapping[str, object], Optional[ParserError]]


# args := [ args:expr { ',' args:expr } [','] ]
#   args: Sequence[?] = []


@attr.dataclass
class Combinator(abc.ABC):
    @cached_property
    def variables(self) -> Mapping[str, Type]:
        return {}

    @property
    @abc.abstractmethod
    def result_type(self) -> Type:
        raise NotImplementedError

    @abc.abstractmethod
    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        raise NotImplementedError


@attr.dataclass
class NestedCombinator(Combinator, abc.ABC):
    combinator: Combinator


@attr.dataclass
class TokenCombinator(Combinator):
    """
    This combinator is match token by it's identifier.

    If current token in stream is matched then return syntax token without errors. Otherwise raises parser error
    """
    token_id: TokenID

    @property
    def result_type(self) -> Type:
        return SyntaxToken

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        return parser.consume(self.token_id), {}, None


@attr.dataclass
class ParseletCombinator(Combinator):
    """
    This combinator is match result of call another parselet.
    """
    parser_id: ParseletID
    priority: Optional[int] = None

    @property
    def result_type(self) -> Type:
        return self.parser_id.result_type

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        result, error = parser.parselet(self.parser_id, self.priority)
        return result, {}, error


@attr.dataclass
class CollectionCombinator(Combinator, Sequence[Combinator], abc.ABC):
    """
    Abstract base for all combinators that contains sequence of nested combinators.
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
    This combinator is match sequence of nested combinators.

    If all nested combinators returns without error this combinator return the last result of them.

    If any nested combinator is raised error it's propagated to up combinator
    """

    @property
    def result_type(self) -> Type:
        return self.combinators[-1].result_type

    @cached_property
    def variables(self) -> Mapping[str, Type]:
        variables = {}
        for combinator in self.combinators:
            nested_variables = combinator.variables
            for name, typ in nested_variables.items():
                if name not in variables:
                    variables[name] = typ
                else:
                    variables[name] = merge_sequence_type(variables[name], typ)

        return variables

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        return sequence(parser, context, self.combinators)


@attr.dataclass
class PostfixCombinator(SequenceCombinator):
    """
    This combinator is special version of sequence combinator, that ignored first nested combinator.

    Used only for postfix Pratt, e.g. led action
    """

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        return sequence(parser, context, itertools.islice(self.combinators, 1, None))

    def fixme(self, parser: Parser, context: AbstractParselet, left: object) -> CombinatorResult:
        """ this method is used for fix recursive call in first nested combinator """
        result, namespace, error = self(parser, context)
        first_combinator = self.combinators[0]
        if isinstance(first_combinator, NamedCombinator):
            # noinspection PyUnresolvedReferences
            namespace.update(first_combinator.make_namespace(context, left))
        return result, namespace, error


@attr.dataclass
class NamedCombinator(NestedCombinator):
    name: str

    @property
    def result_type(self) -> Type:
        return self.combinator.result_type

    @cached_property
    def variables(self) -> Mapping[str, Type]:
        return {self.name: self.combinator.result_type}

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        result, _, error = self.combinator(parser, context)
        namespace = self.make_namespace(context, result)
        return result, namespace, error

    def make_namespace(self, context: AbstractParselet, result: object) -> Mapping[str, object]:
        if is_sequence_type(self.combinator.result_type):
            return {self.name: result}
        elif is_sequence_type(context.variables[self.name]):
            return {self.name: (result,)}
        return {self.name: result}


@attr.dataclass
class OptionalCombinator(NestedCombinator):
    """
    This combinator is
    This combinator returns result of nested combinator on success and returns None and error on failure
    """

    @property
    def result_type(self) -> Type:
        return Optional[self.combinator.result_type]

    @cached_property
    def variables(self) -> Mapping[str, Type]:
        nested_variables = self.combinator.variables
        return {name: make_optional_type(typ) for name, typ in nested_variables.items()}

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        with parser.backtrack():
            try:
                return self.combinator(parser, context)
            except ParserError as error:
                return None, {}, error


@attr.dataclass
class RepeatCombinator(NestedCombinator):
    """
    This combinator match zero or more occurrences of nested combinator.

    Return sequence of values from nested combinator
    """

    @property
    def result_type(self) -> Type:
        return Sequence[self.combinator.result_type]

    @cached_property
    def variables(self) -> Mapping[str, Type]:
        nested_variables = self.combinator.variables
        return {name: make_sequence_type(typ) for name, typ in nested_variables.items()}

    def __call__(self, parser: Parser, context: AbstractParselet) -> CombinatorResult:
        items = []
        error = None
        namespace = {}
        while True:
            try:
                with parser.backtrack():
                    result, last_namespace, last_error = self.combinator(parser, context)
            except ParserError as last_error:
                error = ParserError.merge(error, last_error)
                break
            else:
                error = ParserError.merge(error, last_error)
                items.append(result)
                for name, value in last_namespace.items():
                    namespace[name] = [*namespace[name], *value] if name in namespace else value
        return tuple(items), namespace, error


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


def make_named(name: str, *combinators: Union[Combinator, SymbolID]) -> NamedCombinator:
    return NamedCombinator(make_sequence(*combinators), name)


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


def sequence(parser: Parser, context: AbstractParselet, combinators: Iterable[Combinator]) -> CombinatorResult:
    result = None
    error = None
    namespace = {}
    for combinator in combinators:
        try:
            result, last_namespace, last_error = combinator(parser, context)
        except ParserError as last_error:
            raise ParserError.merge(error, last_error)
        else:
            error = ParserError.merge(error, last_error)
            for name, value in last_namespace.items():
                namespace[name] = [*namespace[name], *value] if name in namespace else value

    return result, namespace, error
