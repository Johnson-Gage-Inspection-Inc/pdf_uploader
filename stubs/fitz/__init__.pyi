from typing import Any, Sequence

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

class Point:
    x: float
    y: float
    def __init__(self, x: float, y: float) -> None: ...

class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None: ...

class Pixmap:
    width: int
    height: int
    samples: bytes
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Shape:
    def draw_line(self, p1: Point, p2: Point) -> Shape: ...
    def draw_rect(self, rect: Rect) -> Shape: ...
    def finish(
        self,
        color: Sequence[float] | None = ...,
        fill: Sequence[float] | None = ...,
        width: float = ...,
        closePath: bool = ...,
    ) -> None: ...
    def commit(self) -> None: ...

class Page:
    rect: Rect
    def get_pixmap(
        self,
        *,
        matrix: Matrix | None = ...,
        dpi: int | None = ...,
        colorspace: Any = ...,
        clip: Any = ...,
        alpha: bool = ...,
        annots: bool = ...,
    ) -> Pixmap: ...
    def new_shape(self) -> Shape: ...
    def insert_text(
        self,
        point: Point,
        text: str,
        fontsize: float = ...,
        fontname: str = ...,
        fontfile: str = ...,
        color: Sequence[float] | None = ...,
    ) -> float: ...
    def search_for(
        self,
        text: str,
        clip: Rect | None = ...,
        quads: bool = ...,
    ) -> list[Rect]: ...
    def insert_image(
        self,
        rect: Rect,
        *,
        filename: str | None = ...,
        stream: bytes | None = ...,
        overlay: bool = ...,
    ) -> None: ...

class Document:
    def load_page(self, page_id: int = ...) -> Page: ...
    def close(self) -> None: ...
    def __enter__(self) -> "Document": ...
    def __exit__(self, *args: Any) -> None: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Page: ...
    def new_page(
        self,
        pno: int = ...,
        width: float = ...,
        height: float = ...,
    ) -> Page: ...
    def tobytes(
        self,
        garbage: int = ...,
        deflate: bool = ...,
        clean: bool = ...,
    ) -> bytes: ...

def open(
    filename: str | None = ...,
    *,
    stream: bytes | None = ...,
    filetype: str | None = ...,
    **kwargs: Any,
) -> Document: ...
def get_text_length(
    text: str,
    fontname: str = ...,
    fontsize: float = ...,
) -> float: ...
