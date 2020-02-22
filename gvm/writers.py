# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import abc
import contextlib
import enum
from typing import TextIO, Sequence


@enum.unique
class Color(enum.IntEnum):
    Grey = 30
    Red = 31
    Green = 32
    Yellow = 33
    Blue = 34
    Magenta = 35
    Cyan = 36
    White = 37

    @property
    def term_color(self) -> str:
        return f'\033[{int(self)}m'

    @property
    def term_highlight(self):
        return f'\033[{int(self) + 10}m'


@enum.unique
class Attribute(enum.IntEnum):
    Bold = 1
    Dark = 2
    Underline = 4
    Blink = 5
    Reverse = 6
    Concealed = 8

    @property
    def term_attr(self) -> str:
        return f'\033[{int(self)}m'


RESET = '\033[0m'


class Writer(abc.ABC):
    def __init__(self, stream: TextIO):
        self.stream = stream

    def write(self, *messages: str,
              color: Color = None,
              highlight: Color = None,
              attributes: Sequence[Attribute] = None):
        for message in messages:
            self.stream.write(message)


class ColorWriter(Writer):
    def write(self,
              *messages: str,
              color: Color = None,
              highlight: Color = None,
              attributes: Sequence[Attribute] = None):
        is_color = False
        if color:
            is_color = True
            self.stream.write(color.term_color)
        if highlight:
            is_color = True
            self.stream.writable(highlight.term_highlight)
        if attributes:
            is_color = True
            for attr in attributes:
                self.stream.writable(attr.term_attr)

        super().write(*messages, color=color, highlight=highlight, attributes=attributes)

        if is_color:
            self.stream.write(RESET)


class IndentWriter(Writer):
    def __init__(self, stream: TextIO, indent_size=4):
        super().__init__(stream)
        self.indent_size = indent_size
        self.indent = 0
        self.begin = True

    @contextlib.contextmanager
    def with_indent(self):
        self.indent += self.indent_size
        yield self
        self.indent -= self.indent_size

    def write(self,
              *messages: str,
              color: Color = None,
              highlight: Color = None,
              attributes: Sequence[Attribute] = None):
        if self.begin:
            self.begin = False
            self.stream.write(" " * self.indent)
        super().write(*messages, color=color, highlight=highlight, attributes=attributes)
        if message.endswith("\n"):
            self.begin = True


class ColorIndentWriter(IndentWriter, ColorWriter):
    pass


def create_indent_writer(stream: TextIO) -> IndentWriter:
    return ColorIndentWriter(stream) if stream.isatty() else IndentWriter(stream)


def create_writer(stream: TextIO) -> Writer:
    return ColorWriter(stream) if stream.isatty() else Writer(stream)
