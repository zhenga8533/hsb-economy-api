import base64
import gzip
import io
import json
from datetime import datetime

from nbtlib import Compound


def decode_nbt(item_bytes) -> dict:
    """
    Decode => Decompress => Warp in io.BytesIO to parse the Base64-encoded data

    :param: item_bytes - Base64-encoded item data
    :return: Parsed NBT data as a Compound object
    """

    decoded_data = base64.b64decode(item_bytes)
    decompressed_data = gzip.decompress(decoded_data)
    return Compound.parse(io.BytesIO(decompressed_data))


def update_kuudra_piece(auction: dict, item_id: str, attribute: str, attribute_cost: float) -> None:
    """
    Parses Kuudra item into specific piece data to add to API.

    :param auction: Auction items object to be sent to API.
    :param item_id: Name of item.
    :param attribute: Name of attribute.
    :param attribute_cost: Total value of attribute.
    """

    KUUDRA_PIECES = {"FERVOR", "AURORA", "TERROR", "CRIMSON", "HOLLOW", "MOLTEN"}
    item_ids = item_id.split("_")

    if item_ids[0] in KUUDRA_PIECES:
        armor_piece = auction.setdefault(item_ids[1], {"attributes": {}})

        # Set individual attribute price
        attributes = armor_piece["attributes"]
        current_cost = attributes[attribute]["lbin"] if attribute in attributes else attribute_cost

        if attribute_cost <= current_cost:
            attributes[attribute] = {"lbin": attribute_cost, "timestamp": datetime.now().timestamp()}


def update_lbin(auction: dict, item: dict) -> None:
    """
    Update the lowest BIN price of an item.

    :param: auction - Auction data containing all item information
    :param: item - Single item information to update the BIN price
    :return: None
    """

    if not item["bin"]:
        return

    now = datetime.now().timestamp()
    price = item.get("price", item.get("starting_bid"))
    nbt = decode_nbt(item["item_bytes"])

    tag = nbt[""]["i"][0]["tag"]
    extra_attributes = tag["ExtraAttributes"]

    # Item ID Handling
    item_id = str(extra_attributes.get("id"))
    if item_id == "PET":
        pet_info = json.loads(extra_attributes["petInfo"])
        item_id = f'{pet_info["tier"]}_{pet_info["type"]}'
    elif item_id == "RUNE":
        runes = extra_attributes["runes"]
        runeKey, runeValue = next(iter(runes.items()))
        item_id = f"{runeKey}_{int(runeValue)}"

    # Set initial item data
    if item_id not in auction:
        auction[item_id] = {"lbin": price, "timestamp": now}
    item = auction[item_id]

    # Pet Level Handling
    if extra_attributes.get("petInfo") is not None:
        if "levels" not in auction[item_id]:
            item["levels"] = {}
        pet_level = tag["display"]["Name"].split(" ")[1][0:-1]
        if price <= item["levels"].get(pet_level, {"lbin": price})["lbin"]:
            item["levels"][pet_level] = {"lbin": price, "timestamp": now}
        return

    # Attribute Handling
    attributes = extra_attributes.get("attributes")
    if attributes is not None:
        if "attributes" not in auction[item_id]:
            item["attributes"] = {}
        attribute_keys = sorted(attributes.keys())
        check_combo = True

        # Get lbin single attribute
        for attribute in attribute_keys:
            tier = attributes[attribute]
            if tier > 5:
                check_combo = False
            attribute_cost = price / (2 ** (tier - 1))

            if attribute_cost <= item["attributes"].get(attribute, {"lbin": attribute_cost})["lbin"]:
                item["attributes"][attribute] = {
                    "lbin": attribute_cost,
                    "timestamp": now,
                }

            # Set Kuudra Armor Attributes
            update_kuudra_piece(auction, item_id, attribute, attribute_cost)

        # Get lbin attribute combination
        if "attribute_combos" not in item:
            item["attribute_combos"] = {}
        if check_combo and len(attribute_keys) > 1:
            attribute_combo = " ".join(attribute_keys)
            if price <= item["attribute_combos"].get(attribute_combo, {"lbin": price})["lbin"]:
                item["attribute_combos"][attribute_combo] = {"lbin": price, "timestamp": now}

    # Default BIN Handling
    if price <= auction[item_id]["lbin"]:
        auction[item_id] = {"lbin": price, "timestamp": now}


def increment_lbin(auction: dict, increment: int) -> None:
    """
    Increment the lowest BIN price of all items by a given value.

    :param: auction - Auction data containing all item information
    :param: increment - Value to increment the BIN price by
    :return: None
    """

    now = datetime.now().timestamp()

    for a in auction:
        # Delete item if it is older than 1 week
        item = auction[a]
        if item.get("lbin"):
            if now - item.get("timestamp", now) > 604_800:
                del item
                continue
            else:
                item["lbin"] += increment

        # Increment pet levels, attributes, and attribute combos
        for key in item:
            if key != "levels" and key != "attributes" and key != "attribute_combos":
                continue
            value = item[key]
            delete = []
            for v in value:
                if now - value[v]["timestamp"] > 604_800:
                    delete.append(v)
                else:
                    value[v]["lbin"] += increment

            for d in delete:
                del value[d]


def merge_auctions(auction: dict, new_auction: dict) -> dict:
    """
    Merge new auction data into the existing auction data.

    :param: auction - Existing auction data
    :param: new_auction - New auction data to merge
    :return: Merged auction data
    """

    for item_id, item in new_auction.items():
        if item_id not in auction:
            auction[item_id] = item
        else:
            existing_item = auction[item_id]
            old_lbin = existing_item.get("lbin", float("inf"))
            old_timestamp = existing_item.get("timestamp", 0)
            new_lbin = item.get("lbin", float("inf"))
            new_timestamp = item.get("timestamp", 0)

            # Update if cheaper, 5x more expensive, or older than a week
            if new_lbin < old_lbin or new_lbin > old_lbin * 5 or (new_timestamp - old_timestamp) > 604_800:
                auction[item_id]["lbin"] = new_lbin
                auction[item_id]["timestamp"] = new_timestamp

    return auction
