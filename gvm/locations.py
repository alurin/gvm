# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

import inspect

import attr


@attr.dataclass(order=True, frozen=True, hash=True)
class Position:
    # Line position in a document (one-based).
    line: int = 1

    # Character offset on a line in a document (one-based).
    column: int = 1

    @staticmethod
    def __add(lhs: int, rhs: int, min: int) -> int:
        """Compute max(min, lhs+rhs) (provided min <= lhs)."""
        return rhs + lhs if 0 < rhs or -rhs < lhs else min

    def lines(self, count: int = 1) -> Position:
        """(line related) Advance to the COUNT next lines."""
        if count:
            line = self.__add(self.line, count, 1)
            return Position(line, 1)
        return self

    def columns(self, count: int = 1) -> Position:
        """(column related) Advance to the COUNT next columns."""
        column = self.__add(self.column, count, 1)
        return Position(self.line, column)

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"

    def __repr__(self) -> str:
        return str(self)


@attr.dataclass(order=True, frozen=True, hash=True)
class Location:
    # The location's filename
    filename: str

    # The location's begin position.
    begin: Position = Position()

    # The end's begin position.
    end: Position = Position()

    def step(self) -> Location:
        """Reset initial location to final location."""
        return Location(self.filename, self.end, self.end)

    def columns(self, count: int = 1) -> Location:
        """Extend the current location to the COUNT next columns."""
        end = self.end.columns(count)
        return Location(self.filename, self.begin, end)

    def lines(self, count: int = 1) -> Location:
        """Extend the current location to the COUNT next lines."""
        end = self.end.lines(count)
        return Location(self.filename, self.begin, end)

    def __add__(self, other: Location) -> Location:
        return Location(self.filename, self.begin, other.end)

    def __str__(self) -> str:
        if self.begin == self.end:
            return f"{self.filename}:{self.begin}"
        elif self.begin.line == self.end.line:
            return f"{self.filename}:{self.begin}-{self.end.column}"
        else:
            return f"{self.filename}:{self.begin}-{self.end}"

    def __repr__(self) -> str:
        return str(self)


def py_location(depth: int = 1) -> Location:
    """ Returns location of parent call frame """
    frame = inspect.currentframe()
    for _ in range(0, depth):
        frame = frame.f_back
        if not frame:
            return Location("<unknown>")

    try:
        frameinfo = inspect.getframeinfo(frame)
        position = Position(frameinfo.lineno, 1)
        return Location(frameinfo.filename, position, position)
    finally:
        del frame
