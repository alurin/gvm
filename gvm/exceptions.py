# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import absolute_import, annotations

import io
import itertools
import os
from typing import TextIO, Tuple, Sequence, Optional

import attr

from gvm.locations import Location

DiagnosticLines = Sequence[Tuple[int, str]]

ANSI_COLOR_RED = "\033[31m"
ANSI_COLOR_GREEN = "\x1b[32m"
ANSI_COLOR_BLUE = "\x1b[34m"
ANSI_COLOR_CYAN = "\x1b[36m"
ANSI_COLOR_RESET = "\x1b[0m"


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

    def get_string(self, content: str = None):
        return get_source_string(self.location, self.message, content or self.content)

    def __str__(self) -> str:
        return self.get_string()


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
    for idx, line in itertools.islice(enumerate(stream), at_before, at_after - 2):
        results.append((idx + 1, line.rstrip("\n")))
    return results


def show_source_lines(strings: DiagnosticLines, location: Location, columns: int = None):
    """
    Convert selected lines to error message, e.g.:

    ```
        1 : from module import system =
          : --------------------------^
    ```
    """
    stream = io.StringIO()
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

        stream.write(ANSI_COLOR_CYAN)
        stream.write(s_line)
        stream.write(" : ")
        stream.write(ANSI_COLOR_BLUE)
        for column, char in enumerate(string):
            column += 1
            is_error = False
            if location.begin.line == line:
                is_error = column >= location.begin.column
            if location.end.line == line:
                is_error = is_error and column <= location.end.column

            if is_error:
                stream.write(ANSI_COLOR_RED)
            else:
                stream.write(ANSI_COLOR_GREEN)
            stream.write(char)

        stream.write(ANSI_COLOR_RESET)
        stream.write("\n")

        # write error line
        if location.begin.line <= line <= location.end.line:
            stream.write("·" * width)
            stream.write(" : ")

            for column, char in itertools.chain(enumerate(string), ((len(string), None),)):
                column += 1

                is_error = False
                if location.begin.line == line:
                    is_error = column >= location.begin.column
                if location.end.line == line:
                    is_error = is_error and column <= location.end.column

                if is_error:
                    stream.write(ANSI_COLOR_RED)
                    stream.write("^")
                    stream.write(ANSI_COLOR_RESET)
                elif char is not None:
                    stream.write("·")
            stream.write("\n")

    return stream.getvalue()


def get_source_string(location: Location, message: str, content: str = None) -> str:
    if content:
        lines = select_source_lines(io.StringIO(content), location)
    else:
        lines = load_source_lines(location)
    if lines:
        source = show_source_lines(lines, location)
        return f"[{location}] {message}:\n{source}"
    return f"[{location}] {message}"
