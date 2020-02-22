# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

from typing import TYPE_CHECKING

import attr

from gvm.locations import Location

if TYPE_CHECKING:
    from gvm.language.grammar import TokenID


@attr.dataclass
class SyntaxToken:
    id: TokenID
    value: str
    location: Location


@attr.dataclass
class SyntaxNode:
    pass
