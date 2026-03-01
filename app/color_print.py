# app/color_print.py
import logging
from typing import Callable, Optional

from app.config import LOG_FILE
from colorama import init, Fore, Style

try:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename=LOG_FILE,
        filemode="a",
    )
except FileNotFoundError:
    text = f"Log file not found: {LOG_FILE}"
    logging.critical(text)
    print(Fore.__dict__["RED"] + str(text) + Style.RESET_ALL)
    input("Press Enter to exit...")
    exit(1)


init()  # Initialize colorama

# --- GUI handler hook ---
_gui_handler: Optional[Callable[[str, str], None]] = None
_console_enabled: bool = True


def set_gui_handler(handler: Optional[Callable[[str, str], None]]) -> None:
    """Register a callback for GUI log display.

    handler signature: handler(color_name: str, text: str)
    Called from any thread -- handler must be thread-safe (Qt signals are).
    """
    global _gui_handler
    _gui_handler = handler


def set_console_enabled(enabled: bool) -> None:
    """Disable console output (e.g. for windowed .exe with no console)."""
    global _console_enabled
    _console_enabled = enabled


def _color(text: str | Exception, color):
    if isinstance(text, Exception):
        text = f"{text.__class__.__name__}: {text}"
    text_str = str(text)

    # Console output
    if _console_enabled:
        assert color.upper() in Fore.__dict__, f"Invalid color: {color}"
        print(Fore.__dict__[color.upper()] + text_str + Style.RESET_ALL)

    # GUI output
    if _gui_handler:
        _gui_handler(color.lower(), text_str)


def black(text: str | Exception = ""):  # Headers
    logging.debug(text)
    _color(text, "BLACK")


def red(text: str | Exception = ""):  # Errors and exceptions
    logging.error(text)
    _color(text, "RED")


def green(text: str | Exception = ""):  # Successful
    logging.debug(text)
    _color(text, "GREEN")


def yellow(text: str | Exception = ""):  # Warnings, notices, alerts
    logging.warning(text)
    _color(text, "YELLOW")


def blue(text: str | Exception = ""):  # Informational
    logging.info(text)
    _color(text, "BLUE")


def magenta(
    text: str | Exception = "",
):  # special or significant information, such as system status updates or important notices.
    logging.info(text)
    _color(text, "MAGENTA")


def cyan(text: str | Exception = ""):  # Prompts, user input
    _color(text, "CYAN")


def white(text: str | Exception = ""):  # Default
    logging.debug(text)
    _color(text, "WHITE")
