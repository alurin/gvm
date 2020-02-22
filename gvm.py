# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from gvm.language import Grammar
from gvm.language.helpers import create_combinator_grammar


def main():
    grammar: Grammar = create_combinator_grammar()


if __name__ == '__main__':
    main()
