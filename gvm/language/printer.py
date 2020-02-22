# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import functools
from io import StringIO
from typing import TypeVar, Callable, TextIO, Union, Type

from multimethod import multimethod
from typing_inspect import is_generic_type, is_optional_type, get_args, get_origin

from gvm.language import Grammar, TokenID, ParseletID
from gvm.language.combinators import Combinator, TokenCombinator, ParseletCombinator, SequenceCombinator, \
    NamedCombinator, OptionalCombinator, RepeatCombinator
from gvm.language.grammar import SyntaxPattern, Parselet
from gvm.typing import unpack_type_argument, is_sequence_type
from gvm.writers import Color, Writer, create_writer

T = TypeVar('T')


def _make_to__string(functor: Callable[[Writer, T], None]) -> Callable[[T], str]:
    def to_string(value: T):
        stream = StringIO()
        functor(create_writer(stream), value)
        return stream.getvalue()

    return to_string


def dumper(func) -> Callable[[Union[Writer, TextIO], T], None]:
    @functools.wraps(func)
    def inner_wrapper(stream: Union[Writer, TextIO], value: T):
        func(stream if isinstance(stream, Writer) else create_writer(stream), value)

    if hasattr(func, 'register'):
        inner_wrapper.register = func.register
    inner_wrapper.to_string = _make_to__string(inner_wrapper)
    return inner_wrapper


@dumper
def dump_pattern(stream: Writer, pattern: SyntaxPattern):
    dump_token_id(stream, pattern.token_id)
    stream.write(' ::= ')
    regex_pattern = pattern.pattern.pattern
    stream.write('r"', regex_pattern, '"', color=Color.Magenta)


@dumper
def dump_grammar(stream: Writer, grammar: Grammar):
    for pattern in grammar.patterns:
        if pattern.is_implicit:
            continue

        dump_pattern(stream, pattern)
        stream.write("\n")

    for parser_id in grammar.parselets.values():
        for parselet in grammar.tables[parser_id].parselets:
            dump_parselet(stream, parselet)
            stream.write("\n")


@dumper
def dump_token_id(stream: Writer, token_id: TokenID):
    stream.write(repr(token_id.name) if token_id.is_implicit else token_id.name, color=Color.Red)


@dumper
def dump_parselet_id(stream: Writer, parser_id: ParseletID):
    stream.write(parser_id.name, color=Color.Blue)


@dumper
def dump_parselet(stream: Writer, parselet: Parselet):
    # return f'{self.parser_id.name} := {self.combinator} -> {self.result_type}'
    dump_parselet_id(stream, parselet.parser_id)
    stream.write(' := ')
    dump_combinator(stream, parselet.combinator)
    stream.write(' -> ')
    dump_type(stream, parselet.result_type)


@dumper
@multimethod
def dump_combinator(stream: Writer, combinator: Combinator):
    raise NotImplementedError(f'Writing combinator to stream is not implemented: {type(combinator).__name__}')


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: TokenCombinator):
    dump_token_id(stream, combinator.token_id)


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: ParseletCombinator):
    dump_parselet_id(stream, combinator.parser_id)
    if combinator.priority:
        stream.write('<')
        stream.write(str(combinator.priority), color=Color.Grey)
        stream.write('>')


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: NamedCombinator):
    stream.write(combinator.name, color=Color.Grey)
    stream.write(':')
    if isinstance(combinator.combinator, SequenceCombinator):
        stream.write('( ')
        dump_combinator(stream, combinator.combinator)
        stream.write(' )')
    else:
        dump_combinator(stream, combinator.combinator)


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: OptionalCombinator):
    stream.write('[ ')
    dump_combinator(stream, combinator.combinator)
    stream.write(' ]')


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: RepeatCombinator):
    stream.write('{ ')
    dump_combinator(stream, combinator.combinator)
    stream.write(' }')


@dump_combinator.register
def dump_combinator(stream: Writer, combinator: SequenceCombinator):
    for idx, child in enumerate(combinator.combinators):
        if idx:
            stream.write(' ')
        dump_combinator(stream, child)


@dumper
def dump_type(stream: Writer, typ: Type):
    if is_optional_type(typ):
        stream.write('Optional', color=Color.Green)
        stream.write('[')
        dump_type(stream, unpack_type_argument(typ))
        stream.write(']')
    elif is_sequence_type(typ):
        stream.write('Sequence', color=Color.Green)
        stream.write('[')
        dump_type(stream, unpack_type_argument(typ))
        stream.write(']')
    elif is_generic_type(typ):
        stream.write(get_origin(typ).__name__, color=Color.Green)
        stream.write('[')
        for idx, element in enumerate(get_args(typ)):
            if idx:
                stream.write(', ')
            dump_type(stream, element)
        stream.write(']')
    else:
        stream.write(typ.__name__, color=Color.Green)
