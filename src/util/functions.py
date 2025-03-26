import json
import logging
import os

import requests as rq
from dotenv import load_dotenv

# Cross-platform imports for locking
if os.name == "nt":
    import portalocker
else:
    import fcntl


def fetch_data(url: str, name: str, logger: logging.Logger, cache: bool, params: dict = None) -> dict:
    """
    Fetch data from the API via GET request.

    :param: url - URL to GET from
    :param: logger - Logger to log the response
    :return: API response
    """
    load_dotenv()
    RETRIES = int(os.getenv("RETRIES"))
    TIMEOUT = int(os.getenv("TIMEOUT"))

    for attempt in range(RETRIES):
        try:
            if logger:
                logger.info(f"Fetching data from {url} w/ params {params}...")
            response = rq.get(url, params=params, timeout=TIMEOUT)

            if response.status_code != 200:
                if logger:
                    logger.error(f"Failed to fetch data. Status code: {response.status_code}")
                continue
            elif logger:
                logger.info(f"Fetched data from {url}. Status code: {response.status_code}")

            # Parse the data and cache it if needed
            data = response.json()
            if logger and cache:
                cache_data(data, name, logger)
            return data
        except rq.exceptions.Timeout:
            if logger:
                logger.error(f"Attempt {attempt + 1} timed out while fetching data from {url}.")
        except rq.exceptions.RequestException as e:
            if logger:
                logger.error(f"Attempt {attempt + 1} failed to fetch data from {url}. Error: {e}")

    logger.error(f"Failed to fetch data from {url} after {RETRIES} attempts.")
    exit(1)


def cache_data(data: dict, name: str, logger: logging.Logger) -> None:
    """
    Cache data to a file.

    :param: data - Data to be cached.
    :param: name - Name of the file to cache the data to.
    :param: logger - Logger to log the data.
    :return: None
    """

    # Make sure all directories exist
    os.makedirs("cache", exist_ok=True)

    # Cache the data
    if logger:
        logger.info(f"Caching data to cache/{name}.json...")
    with open(f"cache/{name}.json", "w") as file:
        json.dump(data, file, indent=4)
    if logger:
        logger.info(f"Data cached to cache/{name}.json.")


def send_data(url: str, data: dict, key: str, logger: logging.Logger) -> dict:
    """
    Send data to the API via POST request.

    :param: url - URL to POST to
    :param: data - Data to be sent
    :param: key - API key needed to make a POST request
    :param: logger - Logger to log the response
    :return: API response
    """

    if logger:
        logger.info(f"Sending data to {url}...")
    response = rq.post(url, json=data, params={"key": key})
    if logger:
        logger.info(f"Data sent to {url}. Status code: {response.status_code}")

    return response.json()


def save_data(data: any, name: str, logger: logging.Logger) -> None:
    """
    Save data to a file with cross-platform file locking.

    :param data: Data to be saved.
    :param name: Name of the file to save the data to.
    :param logger: Logger to log the data.
    :return: None
    """
    os.makedirs("data", exist_ok=True)
    path = f"data/{name}"

    logger.info(f"Saving data to {path}...")
    with open(path, "w") as file:
        if os.name == "nt":
            portalocker.lock(file, portalocker.LOCK_EX)
        else:
            fcntl.flock(file, fcntl.LOCK_EX)
        try:
            json.dump(data, file, indent=4)
        finally:
            if os.name == "nt":
                portalocker.unlock(file)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)
    logger.info(f"Data saved to {path}.")


def get_data(name: str, logger: logging.Logger) -> any:
    """
    Get data from a file with cross-platform file locking.

    :param name: Name of the file to retrieve the data from.
    :param logger: Logger to log the data.
    :return: Data from the file, or None if file does not exist.
    """
    path = f"data/{name}"

    if not os.path.exists(path):
        logger.error(f"Failed to get data from {path}. File does not exist.")
        return None

    logger.info(f"Getting data from {path}...")
    with open(path, "r") as file:
        if os.name == "nt":
            portalocker.lock(file, portalocker.LOCK_SH)
        else:
            fcntl.flock(file, fcntl.LOCK_SH)
        try:
            data = json.load(file)
        finally:
            if os.name == "nt":
                portalocker.unlock(file)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)
    logger.info(f"Data retrieved from {path}.")

    return data
