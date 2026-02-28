from typing import Any, IO
from io import BytesIO

class PageObject:
    def rotate(self, angle: int) -> None: ...
    def add_transformation(self, ctm: Any) -> None: ...

class PdfReader:
    pages: list[PageObject]
    def __init__(
        self,
        stream: str | IO[bytes] | BytesIO,
        strict: bool = ...,
        password: str | None = ...,
    ) -> None: ...

class PdfWriter:
    def add_page(self, page: PageObject) -> PageObject: ...
    def write(self, stream: IO[bytes]) -> None: ...
    def __init__(self) -> None: ...
