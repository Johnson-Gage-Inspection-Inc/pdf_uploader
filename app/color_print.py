# app/color_print.py
import logging
from app.config import LOG_FILE

# Logging levels:
# DEBUG: Detailed information, typically of interest only when diagnosing problems.
# INFO: Confirmation that things are working as expected.
# WARNING: An indication that something unexpected happened, or indicative of some problem in the near future.
# ERROR: Due to a more serious problem, the software has not been able to perform some function.
# CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

# Configure logging:
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', filename=LOG_FILE, filemode='a')

colorama_installed = False

try:
    from colorama import init, Fore, Style
    init()  # Initialize colorama
    colorama_installed = True
except ImportError:
    print("Please install colorama: pip install colorama")
    exit(1)


def color(text, color):
    assert color in Fore.__dict__, f"Invalid color: {color}"
    print(Fore.__dict__[color.upper()] + str(text) + Style.RESET_ALL if colorama_installed else str(text))


def black(text):  # Headers
    logging.debug(text)
    color(text, 'BLACK')


def red(text):  # Errors and exceptions
    logging.error(text)
    color(text, 'RED')


def green(text):  # Successful
    logging.debug(text)
    color(text, 'GREEN')


def yellow(text):  # Warnings, notices, alerts
    logging.warning(text)
    color(text, 'YELLOW')


def blue(text):  # Informational
    logging.info(text)
    color(text, 'BLUE')


def magenta(text):  # special or significant information, such as system status updates or important notices.
    logging.debug(text)
    color(text, 'MAGENTA')


def cyan(text):  # Prompts, user input
    logging.debug(text)
    color(text, 'CYAN')


def white(text):  # Default
    logging.debug(text)
    color(text, 'WHITE')
