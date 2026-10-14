"""Small shared public argument types without backend imports."""

from os import PathLike
from typing import Literal

StrPath = str | PathLike[str]
NumericDateOrder = Literal["mdy", "dmy"]
LanguageCheck = Literal["none", "script", "all"]
