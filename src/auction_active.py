import logging
import os

from dotenv import load_dotenv

from util.functions import fetch_data, get_data, save_data
from util.items import update_lbin
from util.logger import setup_logger


def get_active_auction(logger: logging.Logger = None) -> dict:
    """
    Fetch auction data and process items lbin data.

    :param logger: The logger to use.
    :return: A dictionary containing the auction data.
    """

    # Fetch last parsed timestamp
    last_update = get_data("auction_active_timestamp", logger) or 0

    # Fetch and save latest auction timestamp
    data = fetch_data(
        "https://api.hypixel.net/v2/skyblock/auctions", "auction_active", logger, True, params={"page": 0}
    )
    total_pages = data["totalPages"]
    first_bin = next((auction for auction in data["auctions"] if auction["bin"]), None)
    timestamp = first_bin["start"] if first_bin else float("inf")
    save_data(timestamp, "auction_active_timestamp", logger)

    # Fetch last parsed auction
    auction = get_data("auction.json", logger) or {}

    # Parse through all pages
    for page in range(0, total_pages - 1):
        data = fetch_data(
            "https://api.hypixel.net/v2/skyblock/auctions",
            f"auction_active_{page}",
            logger,
            False,
            params={"page": page},
        )
        auctions = data["auctions"]

        for item in auctions:
            # Stop checking if the auction is older than the last update
            if item["start"] <= last_update:
                if logger:
                    logger.info("Reached the last updated auction.")
                return auction

            update_lbin(auction=auction, item=item)

        # Save and return the auction data
        save_data(auction, "auction.json", logger)
    return auction


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    INCREMENT = int(os.getenv("INCREMENT"))
    KEY = os.getenv("KEY")
    LOG = os.getenv("LOG") == "True"
    URL = os.getenv("AUCTION_URL")
    logger = setup_logger("auction_active", "logs/auction_active.log") if LOG else None

    # Fetch data
    get_active_auction(logger=logger)
