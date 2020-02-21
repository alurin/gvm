# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import re


# noinspection PyPep8Naming
class cached_property(object):
    """
    This modified version from https://habr.com/ru/post/159099/ that works with `abc.ABC`
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, cls=None):
        if instance is not None:
            result = instance.__dict__[self.func.__name__] = self.func(instance)
            return result
        return None  # ABC


def is_camel_case(s):
    """
        tests = [
        "camel",
        "camelCase",
        "CamelCase",
        "CAMELCASE",
        "camelcase",
        "Camelcase",
        "Case",
        "camel_case",
    ]
    :param s:
    :return:
    """
    return s != s.lower() and s != s.upper() and "_" not in s


def camel_case_to_lower(name):
    parts = re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', name)).split()
    return ' '.join(map(str.lower, parts))
