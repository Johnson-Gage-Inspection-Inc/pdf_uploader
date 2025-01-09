# app/color_print.py
import logging
from config import LOG_FILE

# Logging levels:
# DEBUG: Detailed information, typically of interest only when diagnosing problems.
# INFO: Confirmation that things are working as expected.
# WARNING: An indication that something unexpected happened, or indicative of some problem in the near future.
# ERROR: Due to a more serious problem, the software has not been able to perform some function.
# CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

# Configure logging:
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', filename=LOG_FILE, filemode='w')

colorama_installed = False

try:
    from colorama import init, Fore, Style
    init()  # Initialize colorama
    colorama_installed = True
except ImportError:
    print("Please install colorama: pip install colorama")
    exit(1)


def black(text):  # Headers
    print(Fore.BLACK + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def red(text):  # Errors and exceptions
    logging.error(text)
    print(Fore.RED + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def green(text):  # Successful
    logging.debug(text)
    print(Fore.GREEN + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def yellow(text):  # Warnings, notices, alerts
    logging.warning(text)
    print(Fore.YELLOW + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def blue(text):  # Informational
    logging.info(text)
    print(Fore.BLUE + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def magenta(text):  # special or significant information, such as system status updates or important notices.
    logging.debug(text)
    print(Fore.MAGENTA + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def cyan(text):  # Prompts, user input
    logging.debug(text)
    print(Fore.CYAN + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def white(text):  # Default
    logging.debug(text)
    print(Fore.WHITE + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))
