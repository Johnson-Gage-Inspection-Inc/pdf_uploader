# connectivity.py
import subprocess
from os.path import exists
from app.config import SHAREPOINT_PATH
from app.color_print import yellow as warn
from time import sleep


def ping_address(address: str) -> bool:
    """Ping an address to check connectivity.

    Args:
        address (str): The address to ping.

    Returns:
        bool: True if the address is reachable, False otherwise.
    """
    try:
        param = '-n' if subprocess.os.name == 'nt' else '-c'
        result = subprocess.run(
            ['ping', param, '1', address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception as e:
        warn(f"Ping error: {e}")
        return False


def is_internet_connected() -> bool:
    """Check if the internet is connected by pinging Google.

    Returns:
        bool: True if the internet is connected, False otherwise.
    """
    return ping_address("8.8.8.8")


def is_sharepoint_accessible() -> bool:
    # Verify that the SharePoint directory exists
    return exists(SHAREPOINT_PATH)


def is_qualer_accessible() -> bool:
    try:
        while True:
            # Attempt to ping the Qualer endpoint
            if ping_address('qualer.com'):
                return True
            else:
                warn("Qualer server unreachable. Retrying...")
                sleep(5)
    except Exception as e:
        warn(f"Error accessing Qualer: {e}")
        return False


def check_connectivity():
    if not is_internet_connected():
        warn("Warning: Internet is not connected. Please check your connection.")
        return False
    elif not is_sharepoint_accessible():
        warn("Warning: SharePoint directory is not accessible.")
        return False
    elif not is_qualer_accessible():
        warn("Warning: Qualer server is not accessible.")
        return False
    else:
        return True


if __name__ == "__main__":
    check_connectivity()
