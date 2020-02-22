# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import absolute_import, annotations

import io
import itertools
import os
from io import StringIO
from typing import TextIO, Tuple, Sequence, Optional

import attr

from gvm.locations import Location
from gvm.writers import Color, Writer, create_writer

DiagnosticLines = Sequence[Tuple[int, str]]


class GVMError(Exception):
    pass


@attr.dataclass
class DiagnosticError(GVMError):
    """
    The Diagnostic class is represented a diagnostic, such as a compiler error or warning.

    Attributes:
        location - The location at which the message applies
        severity - The diagnostic's severity.
        message  - The diagnostic's message.
        source   - A human-readable string describing the source of this diagnostic, e.g. 'orcinus' or 'doxygen'.
    """
    location: Location
    message: str
    content: Optional[str] = None

    def to_stream(self, stream: Writer, content: str = None):
        dump_source_string(stream, self.location, self.message, content or self.content)

    def __str__(self) -> str:
        stream = StringIO()
        self.to_stream(create_writer(stream))
        return stream.getvalue()


def load_source_lines(location: Location, before: int = 2, after: int = 2) -> DiagnosticLines:
    """ Load selected line and it's neighborhood lines """
    try:
        with open(location.filename, 'r', encoding='utf-8') as stream:
            return select_source_lines(stream, location, before, after)
    except IOError:
        return []


def select_source_lines(stream: TextIO, location: Location, before: int = 2, after: int = 2) -> DiagnosticLines:
    at_before = max(0, location.begin.line - before)
    at_after = location.end.line + after

    results = []
    for idx, line in itertools.islice(enumerate(stream), at_before, at_after):
        line = line.rstrip("\n")
        results.append((idx + 1, line))

    begin = next((i for i, (_, x) in enumerate(results) if x.strip()), 0)
    end = len(results) - next((i for i, (_, x) in enumerate(reversed(results)) if x.strip()), 0)

    return results[begin: end]


def dump_source_lines(stream: Writer, strings: DiagnosticLines, location: Location, columns: int = None):
    """
    Convert selected lines to error message, e.g.:

    ```
        1 : from module import system =
          : --------------------------^
    ```
    """
    if not columns:
        try:
            _, columns = os.popen('stty size', 'r').read().split()
        except (ValueError, IOError):
            columns = 80

    if not strings:
        return

    width = 5
    for idx, _ in strings:
        width = max(len(str(idx)), width)

    for line, string in strings:
        s_line = str(line).rjust(width)

        stream.write(s_line, " : ", color=Color.Cyan)
        for column, char in enumerate(string):
            column += 1
            is_error = False
            if location.begin.line == line:
                is_error = column >= location.begin.column
            if location.end.line == line:
                is_error = is_error and column <= location.end.column

            if is_error:
                stream.write(char, color=Color.Red)
            else:
                stream.write(char, color=Color.Green)
        stream.write("\n")

        # write error line
        if location.begin.line <= line <= location.end.line:
            stream.write(" " * width)
            stream.write(" : ", color=Color.Cyan)

            for column, char in itertools.chain(enumerate(string), ((len(string), None),)):
                column += 1

                is_error = False
                if location.begin.line == line:
                    is_error = column >= location.begin.column
                if location.end.line == line:
                    is_error = is_error and column <= location.end.column

                if is_error:
                    stream.write("^", color=Color.Red)
                elif char is not None:
                    stream.write(" ")
            stream.write("\n")


def dump_source_string(stream: Writer, location: Location, message: str, content: str = None):
    stream.write('[')
    stream.write(str(location))
    stream.write('] ')
    stream.write(message, color=Color.Red)
    stream.write('\n')

    if content:
        lines = select_source_lines(io.StringIO(content), location)
    else:
        lines = load_source_lines(location)
    if lines:
        dump_source_lines(stream, lines, location)
