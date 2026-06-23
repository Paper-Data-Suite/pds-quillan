"""Argument conversion helpers used only by the Quillan CLI."""

from __future__ import annotations

import argparse
import math


class ScoreArgumentError(Exception):
    """Raised for handled set-score numeric argument failures."""


def positive_integer(value: str) -> int:
    """Parse a positive integer argument."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_integer(value: str) -> int:
    """Parse a non-negative integer argument."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "must be a non-negative integer"
        ) from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def location_value(value: str) -> int | str:
    """Parse a non-empty location value, retaining numeric values as integers."""
    stripped = value.strip()
    if not stripped:
        raise argparse.ArgumentTypeError("must be a non-empty value")
    try:
        return int(stripped)
    except ValueError:
        return stripped


def non_negative_number(value: str) -> int | float:
    """Parse a finite number greater than or equal to zero."""
    try:
        parsed = _finite_number(value)
    except argparse.ArgumentTypeError as error:
        raise ScoreArgumentError(str(error)) from error
    if parsed < 0:
        raise ScoreArgumentError(
            "must be a finite number greater than or equal to zero"
        )
    return parsed


def positive_number(value: str) -> int | float:
    """Parse a finite number greater than zero."""
    try:
        parsed = _finite_number(value)
    except argparse.ArgumentTypeError as error:
        raise ScoreArgumentError(str(error)) from error
    if parsed <= 0:
        raise ScoreArgumentError("must be a finite number greater than zero")
    return parsed


def _finite_number(value: str) -> int | float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a finite number") from error
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a finite number")
    return int(parsed) if parsed.is_integer() else parsed
