#!/usr/bin/python3

import os
import subprocess
import sys
import datetime
import calendar
import requests
import shutil
import logging
from dateutil import tz
import pathlib
import time
import configparser
import json
import vimeo
import sys
import argparse

configs = ["dhconfig.txt", "bhconfig.txt"]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--config",
    required=True,
    choices=configs,
    help="filename - dhconfig.txt or bhconfig.txt",
)
parser.add_argument(
    "--fromhour",
    required=True,
    type=int,
    help="Enter start hour in range to gather timelapses as 2-digit integer",
)
parser.add_argument(
    "--tohour",
    required=True,
    type=int,
    help="Enter end hour in range to gather timelapses as 2-digit integer",
)
args = parser.parse_args()

config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), args.config)
config.read(config_file)

timelapse_dir = config["directories"]["timelapse_dir"]
upload_log_location = config["logging"]["upload_log_location"]
log_dir = config["directories"]["log_dir"]
token = config["vimeo"]["token"]
secret = config["vimeo"]["secret"]
key = config["vimeo"]["key"]
slackhook = config["slack"]["slackhook"]
slackheaders = config["slack"]["slackheaders"]
slackheaders = json.loads(slackheaders)


v = vimeo.VimeoClient(token=token, key=key, secret=secret)

# setup logging - log to file needs to be configured  server
file_handler = logging.FileHandler(filename=upload_log_location)
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]

logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
    handlers=handlers,
)

# define timezones for time manipulation
utc_tz = tz.gettz("UTC")
local_tz = tz.gettz("America/New_York")

directions = ["North", "East", "South", "West"]

today = datetime.datetime.today()
start_time = today.replace(hour=args.fromhour, minute=00, second=00).astimezone(
    local_tz
)
end_time = today.replace(hour=args.tohour, minute=59, second=00).astimezone(local_tz)


def create_video_dict(source_directory, start_time, end_time, local_tz):
    """create a dict of file names of videos and paths from a source directory by time"""
    video_dict = {}
    count = 0
    for file in os.listdir(source_directory):
        filename = os.fsdecode(file)
        filename = source_directory + filename
        fname = pathlib.Path(filename)
        mtime = datetime.datetime.fromtimestamp(fname.stat().st_mtime)
        mtime = mtime.replace(tzinfo=local_tz)
        if filename.endswith(".mp4") and mtime >= start_time and mtime <= end_time:
            video_dict[file] = filename
            count += 1
        else:
            continue
    logging.info(
        str(count) + " videos " + str(start_time) + "  until  " + str(end_time)
    )
    return video_dict


def youtube_title_builder(video_dict):
    """create dict of titles to upload to youtube"""
    youtube_title_dict = {}
    for key, value in video_dict.items():
        keytime = key[:10]
        try:
            keytime = datetime.datetime.strptime(keytime, "%Y-%m-%d")
        except ValueError:
            continue
        keytime = keytime.replace(tzinfo=local_tz)
        if "fourway" in key and "daylight" in key:
            youtube_title_dict[key] = keytime.strftime(
                "%B" + " " + "%d" + "," + " " + "%Y" + " - " + config["titles"]["day"]
            )
        if "fourway" in key and "darkness" in key:
            youtube_title_dict[key] = keytime.strftime(
                "%B" + " " + "%d" + "," + " " + "%Y" + " - " + config["titles"]["night"]
            )
    return youtube_title_dict


def vimeo_title_builder(video_dict):
    """create dict of titles to upload to vimeo"""
    vimeo_title_dict = {}
    for key, value in video_dict.items():
        print(key)
        print(value)
        keytime = key[:10]
        try:
            keytime = datetime.datetime.strptime(keytime, "%Y-%m-%d")
        except ValueError:
            continue
        keytime = keytime.replace(tzinfo=local_tz)

        if "darkness" in key and "west" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - West "
                + config["titles"]["night"]
            )
        if "darkness" in key and "east" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - East "
                + config["titles"]["night"]
            )
        if "darkness" in key and "south" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - South "
                + config["titles"]["night"]
            )
        if "darkness" in key and "north" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - North "
                + config["titles"]["night"]
            )

        if "daylight" in key and "south" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - South "
                + config["titles"]["day"]
            )
        if "daylight" in key and "north" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - North "
                + config["titles"]["day"]
            )
        if "daylight" in key and "east" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - East "
                + config["titles"]["day"]
            )
        if "daylight" in key and "west" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B"
                + " "
                + "%d"
                + ","
                + " "
                + "%Y"
                + " - West "
                + config["titles"]["day"]
            )
        if "fourway" in key and "daylight" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B" + " " + "%d" + "," + " " + "%Y" + " - " + config["titles"]["day"]
            )

        if "fourway" in key and "darkness" in key:
            vimeo_title_dict[key] = keytime.strftime(
                "%B" + " " + "%d" + "," + " " + "%Y" + " - " + config["titles"]["night"]
            )
    return vimeo_title_dict


def upload_video_vimeo(vimeo_title_dict, video_dict):
    """vimeo video upload"""
    vimeo_links_dict = {}
    count = 0
    for key in vimeo_title_dict:
        data = {"name": vimeo_title_dict[key]}
        video_uri = v.upload(video_dict[key], data=data)
        video_data = v.get(video_uri + "?fields=link").json()
        link = video_data["link"]
        vimeo_links_dict[video_dict[key]] = link
        count += 1
        logging.info(key + " @ " + link + " uploaded to vimeo.")
    slackjson = {
        "text": str(count) + " Videos uploaded to https://vimeo.com/bostontimelapse"
    }
    r = requests.post(slackhook, json=slackjson, headers=slackheaders)
    if r.status_code == 200:
        logging.info("Slack Message Sent." + str(slackjson))
    else:
        logging.error("Slack Notification Failed")
    return vimeo_links_dict


def main():
    video_dict = create_video_dict(timelapse_dir, start_time, end_time, local_tz)
    f = open(log_dir + "videodict.json", "w")
    dict = json.dumps(video_dict)
    f.write(dict)
    f.close()
    youtube_title_dict = youtube_title_builder(video_dict)
    logging.info(youtube_title_dict)
    f = open(log_dir + "youtube.json", "w")
    dict = json.dumps(youtube_title_dict)
    f.write(dict)
    f.close()
    vimeo_title_dict = vimeo_title_builder(video_dict)
    logging.info(vimeo_title_dict)
    vimeo_links_dict = upload_video_vimeo(vimeo_title_dict, video_dict)
    f = open(log_dir + "vimeolinks.json", "w")
    dict = json.dumps(vimeo_links_dict)
    f.write(dict)
    f.close()
    logging.info("Vimeo upload and youtube prep script ran successfully.")


if __name__ == "__main__":
    main()
