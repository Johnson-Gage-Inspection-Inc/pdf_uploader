# app/color_print.py

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
    print(Fore.RED + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def green(text):  # Successful
    print(Fore.GREEN + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def yellow(text):  # Warnings, notices, alerts
    print(Fore.YELLOW + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def blue(text):  # Informational
    print(Fore.BLUE + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def magenta(text):  # special or significant information, such as system status updates or important notices.
    print(Fore.MAGENTA + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def cyan(text):  # Prompts, user input
    print(Fore.CYAN + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))


def white(text):  # Default
    print(Fore.WHITE + str(text) + Style.RESET_ALL) if colorama_installed else print(str(text))
