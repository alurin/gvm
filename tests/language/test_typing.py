from typing import Optional, Sequence, List

from gvm.typing import unpack_type_arguments, merge_sequence_type, make_optional_type, make_sequence_type


def test_unpack_type_arguments():
    assert unpack_type_arguments(Optional[int]) is int
    assert unpack_type_arguments(Sequence[int]) is int
    assert unpack_type_arguments(List[int]) is List[int]
    assert unpack_type_arguments(int) is int


def test_merge_sequence_type():
    assert merge_sequence_type(int, int) == Sequence[int]
    assert merge_sequence_type(Sequence[int], int) == Sequence[int]
    assert merge_sequence_type(int, Sequence[int]) == Sequence[int]
    assert merge_sequence_type(Optional[int], Sequence[int]) == Sequence[int]
    assert merge_sequence_type(Sequence[int], Optional[int]) == Sequence[int]
    assert merge_sequence_type(Optional[int], Optional[int]) == Sequence[int]
    assert merge_sequence_type(int, Optional[int]) == Sequence[int]
    assert merge_sequence_type(Optional[int], int) == Sequence[int]


def test_make_sequence_type():
    assert make_sequence_type(int) == Sequence[int]
    assert make_sequence_type(Optional[int]) == Sequence[int]
    assert make_sequence_type(Sequence[int]) == Sequence[int]


def test_make_optional_type():
    assert make_optional_type(int) == Optional[int]
    assert make_optional_type(Optional[int]) == Optional[int]
    assert make_optional_type(Sequence[int]) == Sequence[int]
