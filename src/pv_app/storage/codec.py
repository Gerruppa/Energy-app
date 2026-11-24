"""Obiekty domeny (zamrożone dataclassy) ↔ JSON, bez utraty typów (Decimal, date, enum)."""

import dataclasses
import json
import types
import typing
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


def to_json(obj: object) -> str:
    return json.dumps(_encode(obj), ensure_ascii=False, separators=(",", ":"))


def from_json[T](cls: type[T], text: str) -> T:
    return typing.cast(T, _decode(cls, json.loads(text)))


def _encode(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal | date):
        return str(value) if isinstance(value, Decimal) else value.isoformat()
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    return value


def _decode(tp: Any, value: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin in (types.UnionType, typing.Union):
        if value is None:
            return None
        (inner,) = [arg for arg in typing.get_args(tp) if arg is not type(None)]
        return _decode(inner, value)
    if origin is tuple:
        item_type = typing.get_args(tp)[0]
        return tuple(_decode(item_type, item) for item in value)
    if dataclasses.is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        return typing.cast(Any, tp)(
            **{f.name: _decode(hints[f.name], value[f.name]) for f in dataclasses.fields(tp)}
        )
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)
    if tp is Decimal:
        return Decimal(value)
    if tp is date:
        return date.fromisoformat(value)
    return value
