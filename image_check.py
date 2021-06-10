#!/usr/bin/python

import os
import pathlib
import datetime
import requests
import logging
from dateutil import tz
import configparser
import argparse
import json
import requests

def count_images_between_string_time_infilename(
    source_directory, start_time, end_time, local_tz
):
    """group images together by string time in their file name and copy them to a target directory"""
    count = 0
    for file in os.listdir(source_directory):
        filename = os.fsdecode(file)
        filepath = source_directory + filename
        fname = pathlib.Path(filepath)
        if filepath.endswith(".jpg"):
            filetime = filename[:14]
            filetime = datetime.datetime.strptime(filetime, "%Y%m%d_%H-%M")
            filetime = filetime.replace(tzinfo=local_tz)
            if filetime >= start_time and filetime <= end_time:
                count += 1
            else:
                continue
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        required=True,
        help="filename - dhconfig.txt or bhconfig.txt",
    )
    args = parser.parse_args()
    config = configparser.ConfigParser()
    config_file = os.path.join(os.path.dirname(__file__), args.config)
    config.read(config_file)
    image_storage_root_directory = config["directories"]["image_storage_root_directory"]
    image_check_location = config["logging"]["image_check_location"]
    slackhook = config["slack"]["slackhook"]
    slackheaders = config["slack"]["slackheaders"]

    # convert srting config inputs to dicts so they are read correctly
    slackheaders = json.loads(slackheaders)

    logging.basicConfig(
        filename=image_check_location,
        format="%(asctime)s - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
        level=logging.INFO,
    )


    local_tz = tz.gettz("America/New_York")
    today = datetime.datetime.today()
    start_time = today.replace(hour=00, minute=00, second=00).astimezone(local_tz)
    end_time = today.replace(hour=23, minute=59, second=59).astimezone(local_tz)

    directions = ["north", "east", "south", "west"]
    stats_dict = {"north": {"#images": 0, "#missing": 0}, "east": {"#images": 0, "#missing": 0}, "south": {"#images": 0, "#missing": 0}, "west": {"#images": 0, "#missing": 0}}

    for i in directions:
        source_directory = image_storage_root_directory + i
        count = count_images_between_string_time_infilename(source_directory, start_time, end_time, local_tz)
        expected_count = (today.hour * 60) + today.minute
        difference = expected_count - count
        stats_dict[i]['#images'] = count
        stats_dict[i]['#missing'] = difference

    logging.info(stats_dict)

    slackjson = {
        "text": args.config + " " + str(stats_dict)
    }
    r = requests.post(slackhook, json=slackjson, headers=slackheaders)

if __name__ == "__main__":
    main()
