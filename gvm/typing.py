# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Sequence
from typing import Type, Sequence as TypeSequence, Optional

import typing_inspect
from typing_inspect import is_optional_type


def is_sequence_type(typ: Type) -> bool:
    return typing_inspect.get_origin(typ) is Sequence


def unpack_type_arguments(typ: Type) -> Type:
    if is_optional_type(typ) or is_sequence_type(typ):
        return typing_inspect.get_args(typ)[0]
    return typ


def merge_sequence_type(lhs: Type, rhs: Type) -> Type:
    """ Combine type to sequence """
    lhs = unpack_type_arguments(lhs)
    rhs = unpack_type_arguments(rhs)
    if lhs != rhs:
        raise TypeError(f"Can not merge types: lhs and rhs")

    return TypeSequence[lhs]


def make_sequence_type(typ: Type) -> TypeSequence:
    typ = unpack_type_arguments(typ)
    return TypeSequence[typ]


def make_optional_type(typ: Type) -> Optional:
    if is_sequence_type(typ) or is_optional_type(typ):
        return typ
    return Optional[typ]


def make_default_mutable_value(typ: Type) -> object:
    if is_sequence_type(typ):
        return []
    return None
