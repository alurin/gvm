# Copyright (C) 2019-2020 Vasiliy Sheredeko
#
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.
import abc
import typing
from typing import Type, Callable

import attr

from gvm.language.combinators import Combinator


@attr.dataclass(frozen=True, order=False, eq=False)
class Action:
    """
    Action is used for convert result and namespace of combinators to result of parselet.

    E.g. create syntax nodes or collections of nodes
    """

    @property
    @abc.abstractmethod
    def result_type(self) -> Type:
        """ Return type of this action """
        raise NotImplementedError

    @abc.abstractmethod
    def __call__(self, result, namespace: dict):
        raise NotImplementedError


@attr.dataclass(frozen=True, order=False, eq=False)
class ReturnResultAction(Action):
    __result_type: Type

    @property
    def result_type(self) -> Type:
        return self.__result_type

    def __call__(self, result, namespace: dict):
        return result


@attr.dataclass(frozen=True, order=False, eq=False)
class ReturnVariableAction(Action):
    name: str
    __result_type: Type

    @property
    def result_type(self) -> Type:
        return self.__result_type

    def __call__(self, result, namespace: dict):
        return namespace[self.name]


@attr.dataclass(frozen=True, order=False, eq=False)
class CallAction(Action):
    functor: Callable
    __result_type: Type

    @property
    def result_type(self) -> Type:
        return self.__result_type

    def __call__(self, result, namespace: dict):
        return self.functor(**namespace)


ActionGenerator = Callable[[Combinator], Action]


def make_return_result() -> ActionGenerator:
    """ Returns action that returns value of variable as result of parselet """

    def make_action(combinator: Combinator):
        return ReturnResultAction(combinator.result_type)

    return make_action


def make_return_attribute(name: str) -> ActionGenerator:
    """ Returns action that returns value of variable as result of parselet """

    def make_action(combinator: Combinator):
        variables = combinator.variables
        result_type = variables[name]
        return ReturnVariableAction(variables, result_type)

    return make_action


def make_ctor(ctor: Type) -> ActionGenerator:
    def make_action(_: Combinator):
        return CallAction(ctor, ctor)

    return make_action


def make_call(functor: Callable, return_type: Type = None) -> ActionGenerator:
    def make_action(_: Combinator):
        return CallAction(functor, return_type)

    if not return_type:
        hints = typing.get_type_hints(return_type)
        breakpoint()

    return make_action
