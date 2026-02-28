from typing import Any

class TesseractError(Exception): ...

class PyTesseract:
    tesseract_cmd: str

pytesseract: PyTesseract

def image_to_string(image: Any, lang: str | None = ..., config: str = ..., **kwargs: Any) -> str: ...
def image_to_osd(image: Any, lang: str = ..., config: str = ..., **kwargs: Any) -> str: ...
