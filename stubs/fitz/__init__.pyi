from typing import Any

class Matrix:
    def __init__(
        self,
        a: float = 1,
        b: float = 0,
        c: float = 0,
        d: float = 1,
        e: float = 0,
        f: float = 0,
    ) -> None: ...

class Pixmap:
    width: int
    height: int
    samples: bytes
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Page:
    def get_pixmap(
        self,
        *,
        matrix: Matrix | None = ...,
        dpi: int | None = ...,
        colorspace: Any = ...,
        clip: Any = ...,
        alpha: bool = ...,
        annots: bool = ...
    ) -> Pixmap: ...

class Document:
    def load_page(self, page_id: int = ...) -> Page: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Document": ...
    def __exit__(self, *args: Any) -> None: ...

def open(filename: str | None = ..., **kwargs: Any) -> Document: ...
