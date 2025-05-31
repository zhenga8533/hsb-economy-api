import json
import logging
import os

import requests as rq
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Cross-platform imports for locking
if os.name == "nt":
    import portalocker
else:
    import fcntl


# Load environment variables
load_dotenv()
RETRIES = int(os.getenv("RETRIES", "3"))
TIMEOUT = int(os.getenv("TIMEOUT", "10"))

# Set up a session with retry logic
session = rq.Session()
adapter = HTTPAdapter(
    max_retries=Retry(
        total=RETRIES,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
)
session.mount("http://", adapter)
session.mount("https://", adapter)


def fetch_data(url: str, name: str, logger: logging.Logger, cache: bool, params: dict = None) -> dict:
    """
    Fetch data from a given URL with retries and caching.

    :param: url - URL to fetch data from
    :param: name - Name of the file to cache the data to
    :param: logger - Logger to log the fetching process
    :param: cache - Whether to cache the data or not
    :param: params - Additional parameters to pass in the request
    :return: Fetched data as a dictionary
    """

    try:
        if logger:
            logger.info(f"Fetching data from {url} w/ params {params}...")
        response = session.get(url, params=params, timeout=TIMEOUT)

        if response.status_code == 200:
            if logger:
                logger.info(f"Fetched data from {url}. Status code: {response.status_code}")
            data = response.json()
            if logger and cache:
                cache_data(data, name, logger)
            return data
        else:
            if logger:
                logger.error(f"Failed to fetch data. Status code: {response.status_code}")
    except rq.exceptions.Timeout:
        if logger:
            logger.error(f"Timeout while fetching data from {url}.")
    except rq.exceptions.RequestException as e:
        if logger:
            logger.error(f"Request error while fetching data from {url}: {e}")

    logger.error(f"Failed to fetch data from {url} after {RETRIES} attempts.")
    exit(1)


def cache_data(data: dict, name: str, logger: logging.Logger) -> None:
    """
    Cache data to a JSON file.

    :param: data - Data to be cached
    :param: name - Name of the file to cache the data to
    :param: logger - Logger to log the caching process
    :return: None
    """

    os.makedirs("cache", exist_ok=True)
    path = f"cache/{name}.json"

    logger.info(f"Caching data to {path}...")
    if os.name == "nt":
        with portalocker.Lock(path, mode="w", timeout=5) as file:
            json.dump(data, file, indent=4)
    else:
        with open(path, "w") as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX)
                json.dump(data, file, indent=4)
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)
    logger.info(f"Data cached to {path}.")


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
    Save data to a file.

    :param: data - Data to be saved
    :param: name - Name of the file to save the data to
    :param: logger - Logger to log the data
    :return: None
    """

    os.makedirs("data", exist_ok=True)
    path = f"data/{name}"

    logger.info(f"Saving data to {path}...")
    if os.name == "nt":
        with portalocker.Lock(path, mode="w") as file:
            json.dump(data, file, indent=4)
    else:
        with open(path, "w") as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX)
                json.dump(data, file, indent=4)
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)
    logger.info(f"Data saved to {path}.")


def get_data(name: str, logger: logging.Logger) -> any:
    """
    Get data from a file with cross-platform file locking.

    :param name: Name of the file to get data from
    :param logger: Logger to log the data
    :return: Data from the file or None if not found or unreadable
    """
    path = f"data/{name}"

    if not os.path.exists(path):
        logger.error(f"Failed to get data from {path}. File does not exist.")
        return {}

    logger.info(f"Getting data from {path}...")
    try:
        if os.name == "nt":
            with portalocker.Lock(path, mode="r", flags=portalocker.LOCK_SH) as file:
                data = json.load(file)
        else:
            with open(path, "r") as file:
                try:
                    fcntl.flock(file, fcntl.LOCK_SH)
                    data = json.load(file)
                finally:
                    fcntl.flock(file, fcntl.LOCK_UN)
        logger.info(f"Data retrieved from {path}.")
        return data
    except FileNotFoundError:
        logger.error(f"File {path} disappeared before it could be opened.")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from {path}.")
    except Exception as e:
        logger.error(f"Unexpected error reading {path}: {e}")

    return {}
