"""Parse an uploaded two-ticker closing-price CSV, rejecting it rather than repairing it."""

import csv
import io
import math
import re
from datetime import date

import pandas as pd

TICKER = re.compile(r"[A-Z0-9.-]{1,10}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# float() would also take "1_000", " 12 ", "nan" and "infinity"; those are rejected here.
NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")


class InputError(ValueError):
    """A problem with the user's input, reported back to them as a 422."""


def parse_prices(content: bytes, max_bytes: int = 1048576, max_rows: int = 10000) -> pd.DataFrame:
    """Return a Date-indexed frame with `<TICKER>_Close` columns in file order.

    Line numbers in messages count the header as line 1.
    """
    if len(content) > max_bytes:
        raise InputError(f"The file is larger than {max_bytes} bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("The file is not UTF-8 text") from exc
    lines = list(csv.reader(io.StringIO(text, newline="")))
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise InputError("The file is empty")
    header = [name.strip() for name in lines[0]]
    if len(header) != 3 or header[0] != "Date":
        raise InputError("The header must be Date,<TICKER_A>,<TICKER_B>")
    tickers = header[1:]
    for ticker in tickers:
        if not TICKER.fullmatch(ticker):
            raise InputError(f"Ticker {ticker!r} must be 1-10 characters from A-Z, 0-9, '.' and '-'")
    if tickers[0] == tickers[1]:
        raise InputError("The two tickers must differ")
    rows = lines[1:]
    if not rows:
        raise InputError("The file has no price rows")
    if len(rows) > max_rows:
        raise InputError(f"The file has more than {max_rows} price rows")
    dates, values = [], []
    for line, row in enumerate(rows, start=2):
        if len(row) != 3:
            raise InputError(f"Line {line} has {len(row)} fields; expected 3")
        if not DATE.fullmatch(row[0]):
            raise InputError(f"Line {line}: date {row[0]!r} is not in YYYY-MM-DD format")
        try:
            day = date.fromisoformat(row[0])
        except ValueError as exc:
            raise InputError(f"Line {line}: {row[0]} is not a calendar date") from exc
        if dates and day == dates[-1]:
            raise InputError(f"Line {line}: date {row[0]} is repeated")
        if dates and day < dates[-1]:
            raise InputError(f"Line {line}: date {row[0]} is earlier than the line before")
        values.append([_price(cell, ticker, line) for ticker, cell in zip(tickers, row[1:])])
        dates.append(day)
    return pd.DataFrame(values, columns=[f"{t}_Close" for t in tickers],
                        index=pd.DatetimeIndex(dates, name="Date"), dtype=float)


def _price(cell: str, ticker: str, line: int) -> float:
    if cell == "":
        raise InputError(f"Line {line}: the {ticker} price is empty")
    if cell.strip().lower().lstrip("+-") in {"nan", "inf", "infinity"}:
        raise InputError(f"Line {line}: the {ticker} price {cell!r} is not a finite number")
    if not NUMBER.fullmatch(cell):
        raise InputError(f"Line {line}: the {ticker} price {cell!r} is not a number")
    value = float(cell)
    if not math.isfinite(value):
        raise InputError(f"Line {line}: the {ticker} price {cell!r} is not a finite number")
    if value <= 0:
        raise InputError(f"Line {line}: the {ticker} price {cell} must be above zero")
    return value


def tickers(frame: pd.DataFrame) -> list[str]:
    return [column.removesuffix("_Close") for column in frame.columns]
