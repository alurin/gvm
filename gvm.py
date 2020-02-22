# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import sys

from gvm.core import create_core_grammar
from gvm.language import Grammar, DefaultScanner
from gvm.language.helpers import create_combinator_grammar
from gvm.language.parser import Parser, ParserError
from gvm.writers import create_writer


def main():
    grammar = Grammar()

    # core grammar
    grammar.extend(create_core_grammar())

    # combinator grammars
    grammar.extend(create_combinator_grammar())

    # add macro grammar. e.g. expr
    grammar.add_parser('macro', 'name:Name "::=" combinator: combinator_sequence')

    # # dump grammar
    # dump_grammar(sys.stdout, grammar)

    content = """
expr ::= 1 2 3 ; |

def main(): pass
""".strip()

    #
    scanner = DefaultScanner(grammar, '<example>', content)
    parser = Parser(scanner)
    try:
        parser.parse(grammar.parselets['macro'])
    except ParserError as ex:
        ex.to_stream(create_writer(sys.stderr), content)
        exit(1)


if __name__ == '__main__':
    main()
