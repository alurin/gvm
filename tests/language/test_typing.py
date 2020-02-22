from typing import Optional, Sequence, List

from gvm.typing import unpack_type_arguments, merge_sequence_type, make_optional_type, make_sequence_type, is_subclass


def test_unpack_type_arguments():
    assert unpack_type_arguments(Optional[int]) is int
    assert unpack_type_arguments(Sequence[int]) is int
    assert unpack_type_arguments(List[int]) is List[int]
    assert unpack_type_arguments(int) is int


def test_merge_sequence_type():
    assert merge_sequence_type(int, int) == Sequence[int]
    assert merge_sequence_type(Sequence[int], int) == Sequence[int]
    assert merge_sequence_type(int, Sequence[int]) == Sequence[int]
    assert merge_sequence_type(Sequence[int], Sequence[int]) == Sequence[int]
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


def test_is_subclass():
    class_a = type('A', (), {})
    class_b = type('B', (class_a,), {})
    class_c = type('C', (class_a,), {})

    assert is_subclass(int, int)
    assert is_subclass(bool, int)

    assert is_subclass(Sequence[int], Sequence[int])
    assert is_subclass(Sequence[bool], Sequence[int])
    assert not is_subclass(Sequence[bool], Sequence[str])

    assert is_subclass(Optional[bool], Optional[int])
    assert not is_subclass(Optional[str], Optional[int])

    assert is_subclass(class_c, class_a)
    assert not is_subclass(class_a, class_c)

    assert is_subclass(class_b, class_a)
    assert not is_subclass(class_a, class_b)

    assert not is_subclass(class_b, class_c)
    assert not is_subclass(class_c, class_b)
