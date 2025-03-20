import logging
import os

from dotenv import load_dotenv

from util.functions import fetch_data, send_data
from util.logger import setup_logger


def get_bazaar(logger: logging.Logger) -> dict:
    """
    Gets the latest Bazaar data and stores it in the provided 'items' dictionary.

    :param logger: The logger to use.
    :return: A dictionary containing the latest Bazaar data.
    """

    # Fetch the Bazaar data
    data = fetch_data("https://api.hypixel.net/v2/skyblock/bazaar", "bazaar", logger, True)

    # Loop through the products and store the data
    products = data["products"]
    bazaar = {}

    for product in products:
        item = products[product]
        quick_status = item["quick_status"]
        bazaar[product] = [quick_status["sellPrice"], quick_status["buyPrice"]]

    return bazaar


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    KEY = os.getenv("KEY")
    LOG = os.getenv("LOG") == "True"
    URL = os.getenv("BAZAAR_URL")
    logger = setup_logger("bazaar", "logs/bazaar.log") if LOG else None

    # Fetch and send data
    bazaar = get_bazaar(logger=logger)
    send_data(url=URL, data={"items": bazaar}, key=KEY, logger=logger)
