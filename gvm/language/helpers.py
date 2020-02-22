# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import ast
from typing import Sequence, Optional

import attr

from gvm.core import create_core_grammar
from gvm.exceptions import DiagnosticError
from gvm.language.actions import make_ctor, make_return_variable
from gvm.language.combinators import make_sequence, make_repeat, make_named, Combinator, make_optional, make_token, \
    make_parselet
from gvm.language.grammar import Grammar
from gvm.language.parser import Parser
from gvm.language.scanner import DefaultScanner
from gvm.language.syntax import SyntaxToken, SyntaxNode
from gvm.locations import Location, py_location


@attr.dataclass
class CombinatorNode(SyntaxNode):
    pass


@attr.dataclass
class NamedNode(CombinatorNode):
    name: SyntaxToken
    combinator: CombinatorNode


@attr.dataclass
class ReferenceNode(CombinatorNode):
    name: SyntaxToken
    priority: Optional[SyntaxNode] = None


@attr.dataclass
class ImplicitNode(CombinatorNode):
    value: SyntaxToken


@attr.dataclass
class OptionalNode(CombinatorNode):
    combinator: CombinatorNode


@attr.dataclass
class RepeatNode(CombinatorNode):
    combinator: CombinatorNode


@attr.dataclass
class SequenceNode(CombinatorNode):
    combinators: Sequence[CombinatorNode]


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
    number_id = grammar.tokens['Integer']
    colon_id = grammar.add_implicit(':')
    parent_open_id = grammar.tokens['(']
    parent_close_id = grammar.tokens[')']
    square_open_id = grammar.tokens['[']
    square_close_id = grammar.tokens[']']
    curly_open_id = grammar.tokens['{']
    curly_close_id = grammar.tokens['}']
    less_id = grammar.tokens['<']
    great_id = grammar.tokens['>']

    # parse combinator definition
    comb_id = grammar.add_parselet('combinator', result_type=CombinatorNode)
    seq_id = grammar.add_parselet('combinator_sequence', result_type=SequenceNode)

    # combinator := name: Name ":" combinator=combinator            ; named variable
    grammar.add_parser(
        comb_id,
        make_sequence(make_named('name', name_id), colon_id, make_named('combinator', comb_id)),
        make_ctor(NamedNode)
    )

    # combinator := name: Name  [ '<' priority: Number '>' ]        ; reference to parselet or token
    grammar.add_parser(
        comb_id,
        make_sequence(make_named('name', name_id), make_optional(less_id, make_named('priority', number_id), great_id)),
        make_ctor(ReferenceNode)
    )

    # combinator := value: String                                   ; reference to implicit token
    grammar.add_parser(comb_id, make_named('value', string_id), make_ctor(ImplicitNode))

    # combinator := '[' combinator: combinator_sequence ']'         ; optional combinator
    grammar.add_parser(
        comb_id,
        make_sequence(square_open_id, make_named('combinator', seq_id), square_close_id),
        make_ctor(OptionalNode)
    )

    # combinator := '{' combinator: combinator_sequence '}'         ; repeat combinator
    grammar.add_parser(
        comb_id,
        make_sequence(curly_open_id, make_named('combinator', seq_id), curly_close_id),
        make_ctor(RepeatNode)
    )

    # combinator := '(' combinator: combinator_sequence ')'         ; parenthesis combinator
    grammar.add_parser(
        comb_id,
        make_sequence(parent_open_id, make_named('combinator', seq_id), parent_close_id),
        make_return_variable('combinator')
    )

    # combinator_sequence := combinators:combinator combinators:{ combinator }              ; sequence combinator
    grammar.add_parser(
        seq_id,
        make_sequence(make_named('combinators', comb_id), make_named('combinators', make_repeat(comb_id))),
        make_ctor(SequenceNode)
    )

    return grammar


combinator_grammar = create_combinator_grammar()


def parse_combinator(content: str):
    scanner = DefaultScanner(combinator_grammar, '<example>', content)
    parser = Parser(scanner)
    return parser.parse(combinator_grammar.parselets['combinator_sequence'])


def convert_node(grammar: Grammar, node: CombinatorNode, location: Location) -> Combinator:
    if isinstance(node, SequenceNode):
        return make_sequence(*(convert_node(grammar, child, location) for child in node.combinators))
    if isinstance(node, RepeatNode):
        return make_repeat(convert_node(grammar, node.combinator, location))
    if isinstance(node, OptionalNode):
        return make_optional(convert_node(grammar, node.combinator, location))
    if isinstance(node, NamedNode):
        return make_named(node.name.value, convert_node(grammar, node.combinator, location))
    if isinstance(node, ImplicitNode):
        token_id = grammar.add_implicit(ast.literal_eval(node.value.value), location=location)
        return make_token(token_id)
    if isinstance(node, ReferenceNode):
        name = node.name.value
        if name in grammar.tokens:
            if node.priority:
                raise DiagnosticError(location, f'Token combinator can not have priority')
            return make_token(grammar.tokens[name])
        elif name in grammar.parselets:
            priority = node.priority and ast.literal_eval(node.priority.value)
            return make_parselet(grammar.parselets[name], priority)
        else:
            raise DiagnosticError(location, f"Not found symbol {name} in grammar")

    raise NotImplementedError(f'Not implemented conversion from node to combinator: {type(node).__name__}')


def make_combinator(grammar: Grammar, content: str, location: Location = None):
    location = location or py_location(2)
    return convert_node(grammar, parse_combinator(content), location)
