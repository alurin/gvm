# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from tokenize import group as re_group, maybe as re_maybe

from gvm.language.grammar import Grammar

RE_COMMENT = r'#[^\r\n]*'
RE_WHITESPACE = r'[ \f\t]+'
RE_NEWLINE = r'(\r?\n)+'
RE_NAME = r"([^\W\d])([\w-]*[\w])?[?!]*"
RE_NUMBER_HEXADECIMAL = r'0[xX](?:_?[0-9a-fA-F])+'
RE_NUMBER_BINARY = r'0[bB](?:_?[01])+'
RE_NUMBER_OCTAL = r'0[oO](?:_?[0-7])+'
RE_NUMBER_DECIMAL = r'(?:0(?:_?0)*|[1-9](?:_?[0-9])*)'
RE_EXPONENT = r'[eE][-+]?[0-9](?:_?[0-9])*'
RE_FLOAT_POINT = re_group(r'[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?', r'\.[0-9](?:_?[0-9])*') + re_maybe(RE_EXPONENT)
RE_FLOAT_EXPONENT = r'[0-9](?:_?[0-9])*' + RE_EXPONENT
RE_COMPLEX = re_group(r'[0-9](?:_?[0-9])*[jJ]', re_group(RE_FLOAT_POINT, RE_FLOAT_EXPONENT) + r'[jJ]')
RE_STRING_SINGLE = r"'[^\n'\\]*(?:\\.[^\n'\\]*)*'"
RE_STRING_DOUBLE = r'"[^\n"\\]*(?:\\.[^\n"\\]*)*"'


def create_core_grammar() -> Grammar:
    """ This function is used for initialize default grammar """
    grammar = Grammar()
    grammar.add_pattern(grammar.add_token('Comment'), RE_COMMENT)
    grammar.add_pattern(grammar.add_token('Whitespace'), RE_WHITESPACE)
    grammar.add_pattern(grammar.add_token('Name'), RE_NAME)
    grammar.add_pattern(grammar.add_token('NewLine'), RE_NEWLINE)
    grammar.add_pattern(grammar.add_token('String'), RE_STRING_SINGLE)
    grammar.add_pattern(grammar.add_token('String'), RE_STRING_DOUBLE)
    grammar.add_pattern(grammar.add_token('Integer'), RE_NUMBER_BINARY)
    grammar.add_pattern(grammar.add_token('Integer'), RE_NUMBER_OCTAL)
    grammar.add_pattern(grammar.add_token('Integer'), RE_NUMBER_DECIMAL)
    grammar.add_pattern(grammar.add_token('Integer'), RE_NUMBER_HEXADECIMAL)
    grammar.add_pattern(grammar.add_token('Float'), RE_FLOAT_POINT)
    grammar.add_pattern(grammar.add_token('Float'), RE_FLOAT_EXPONENT)
    grammar.add_implicit('(')
    grammar.add_implicit(')')
    grammar.add_implicit('[')
    grammar.add_implicit(']')
    grammar.add_implicit('{')
    grammar.add_implicit('}')
    grammar.add_implicit('<')
    grammar.add_implicit('>')

    grammar.add_trivia(grammar.tokens['Comment'])
    grammar.add_trivia(grammar.tokens['Whitespace'])
    grammar.add_brackets(grammar.tokens['('], grammar.tokens[')'])
    grammar.add_brackets(grammar.tokens['['], grammar.tokens[']'])
    grammar.add_brackets(grammar.tokens['{'], grammar.tokens['}'])

    return grammar
