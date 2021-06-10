#!/usr/bin/python

import os
import subprocess
import datetime
import calendar
import requests
import shutil
import logging
from dateutil import tz
import pathlib
import time
import configparser
import argparse
import json

# read in config from config.txt
processbatch = ["daylight", "darkness", "all", "test"]
imagesfrom = ["today", "yesterday"]
configs = ["dhconfig.txt", "bhconfig.txt"]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--processbatch",
    required=True,
    choices=processbatch,
    help="Run daylight, darkness, both or test",
)
parser.add_argument(
    "--imagesfrom",
    required=True,
    choices=imagesfrom,
    help="Images from yesterday or today",
)
parser.add_argument(
    "--config",
    required=True,
    choices=configs,
    help="filename - dhconfig.txt or bhconfig.txt",
)
args = parser.parse_args()

# ensure config can be read from cron
config = configparser.ConfigParser()
config_file = os.path.join(os.path.dirname(__file__), args.config)
config.read(config_file)

# read in config variables
project_dir = config["directories"]["project_dir"]
timelapse_dir = config["directories"]["timelapse_dir"]
image_storage_root_directory = config["directories"]["image_storage_root_directory"]
log_dir = config["directories"]["log_dir"]
timelapse_log_location = config["logging"]["timelapse_log_location"]
sun_api_boston = config["api_urls"]["sun_api_boston"]
timelapse_config = config["timelapse_config"]["timelapse_config"]
slackhook = config["slack"]["slackhook"]
slackheaders = config["slack"]["slackheaders"]

# convert srting config inputs to dicts so they are read correctly
slackheaders = json.loads(slackheaders)
timelapse_config = json.loads(timelapse_config)

# logging config
logging.basicConfig(
    filename=timelapse_log_location,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)

# list of events to pull from sunrise-sunset.org api calls
events = [
    "sunrise",
    "sunset",
    "civil_twilight_begin",
    "civil_twilight_end",
    "nautical_twilight_begin",
    "nautical_twilight_end",
    "astronomical_twilight_begin",
    "astronomical_twilight_end",
]

# define timezones for time manipulation
utc_tz = tz.gettz("UTC")
local_tz = tz.gettz("America/New_York")

# list of camera directions used for iteration file structure and naming order matters
directions = ["north", "east", "south", "west", "fourway"]


def get_yesterday_string():
    """returns yesterday as a string"""
    yesterday = datetime.datetime.today()
    yesterday -= datetime.timedelta(days=1)
    yesterday = str(yesterday)
    yesterday = yesterday[:-16]
    return yesterday


def get_today_string():
    """returns today as a string"""
    today = datetime.datetime.today()
    today = str(today)
    today = today[:-16]
    return today


def get_tomorrow_string():
    """returns tomorrow as a string"""
    tomorrow = datetime.datetime.today()
    tomorrow += datetime.timedelta(days=1)
    tomorrow = str(tomorrow)
    tomorrow = tomorrow[:-16]
    return tomorrow


def get_sun_data(sun_api_boston, utc_tz, local_tz, yyyy_mm_dd=""):
    """Get data from sunrise-sunset.org api. Defaults to today. Can add optional
    date parameter as string yyyy-mm-dd. Returns dict with keys
    ["sunrise","sunset","solar_noon","day_length","civil_twilight_begin",
    "civil_twilight_end","nautical_twilight_begin","nautical_twilight_end",
    "astronomical_twilight_begin","astronomical_twilight_end"] for events in
    list "events" time is changed to local datetime object from string"""
    sun_api_boston = sun_api_boston + "&date=" + yyyy_mm_dd
    r = requests.get(sun_api_boston)
    # Check if the request was successful
    if r.status_code != 200:
        errormsg = (
            "sunrise-sunet.org not available - API request failed" + r.status_code
        )
        logging.error(errormsg)
        slackjson = {"text": errormsg}
        r = requests.post(slackhook, json=slackjson, headers=slackheaders)
        if r.status_code == 200:
            logging.info("Slack Errror Message Sent." + slackjson)
        else:
            logging.error("Slack Notification Failed")
    else:
        # Log successful request
        logging.info("sunrise-sunset.org api called successfully " + yyyy_mm_dd)
        # store response
        jsonResponse = r.json()
        # create dict with results
    sun_data_dict = jsonResponse["results"]
    for i in events:
        event_str = sun_data_dict[i]
        event_obj = datetime.datetime.strptime(event_str, "%Y-%m-%dT%H:%M:%S+00:00")
        event_obj = event_obj.replace(tzinfo=utc_tz)
        local_event_time = event_obj.astimezone(local_tz)
        sun_data_dict[i] = local_event_time
    return sun_data_dict


def create_directory(path, yyyy_mm_dd, identifier=""):
    """create string for new directory name based on timestamp and optional identifier"""
    path = path + "/" + yyyy_mm_dd
    try:
        new_directory = os.mkdir(path)
        logging.info(path + " directory created.")
    except FileExistsError:
        logging.error("Directory already exists in " + path + " nothing created.")
    path = path + "/" + identifier + "/"
    try:
        new_directory = os.mkdir(path)
        logging.info(path + " directory created.")
    except FileExistsError:
        logging.error("Directory already exists in " + path + " Nothing created.")
    return path


def group_images_between_string_time_infilename(
    source_directory, target_directory, start_time, end_time, local_tz
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
                shutil.copy2(source_directory + "/" + filename, target_directory)
                count += 1
            else:
                continue
    logging.info(
        str(count)
        + " images grabbed from "
        + str(start_time)
        + "  until  "
        + str(end_time)
        + " and copied to "
        + target_directory
        + " for timelapse processing"
    )


def create_weekly_grouping():
    """group images together for each camera by week and save them to a new directory labeled with the week number"""
    target_directory_path_list = []
    today = datetime.datetime.today()
    weekstart = today - datetime.timedelta(days=7)
    weekstart = str(weekstart)
    weekstart = weekstart[:-16]
    weekend = today - datetime.timedelta(days=1)
    weekend = str(weekend)
    weekend = weekend[:-16]

    start_date_dict = get_sun_data(sun_api_boston, utc_tz, local_tz, weekstart)
    end_date_dict = get_sun_data(sun_api_boston, utc_tz, local_tz, weekend)

    weekstart = start_date_dict["sunset"]
    weekend = end_date_dict["civil_twilight_end"]

    for i in directions:
        os.chdir(project_dir + i)
        path = os.getcwd()
        date = datetime.datetime.today()
        week = datetime.datetime.date(date).isocalendar()[1]
        target_directory_path = path + "/" + "full-week-" + str(week)
        try:
            target_directory = os.mkdir(target_directory_path + "/")
            logging.info(target_directory_path + " directory created.")
        except FileExistsError:
            logging.error(
                "Directory already exists in " + os.getcwd() + " Nothing created."
            )
        target_directory_path_list.append(target_directory_path + "/")
        try:
            group_images_between_string_time_infilename(
                path, target_directory_path, weekstart, weekend, local_tz
            )
        except FileNotFoundError:
            logging.error(
                "Directory doesn't exist in " + os.getcwd() + " - no files to copy."
            )
    return target_directory_path_list


def create_monthly_grouping():
    """group images together for each camera by week and save them to a new directory labeled with the week number"""
    today = datetime.datetime.now()
    current_month = datetime.datetime.now().month
    last_month = current_month - 1
    two_months_ago = last_month - 1
    last_month_name = calendar.month_name[last_month]
    last_month_name = last_month_name.lower()
    year = datetime.datetime.now().year
    adaytwomonthsago = today - datetime.timedelta(days=40)
    num_days = calendar.monthrange(year, two_months_ago)[1]
    enddate = today.replace(day=1, hour=00, minute=00, second=00).astimezone(local_tz)
    lastdaytwomonthsago = adaytwomonthsago.replace(
        day=num_days, hour=23, minute=59, second=00
    ).astimezone(local_tz)

    lastdaytwomonthsago = str(lastdaytwomonthsago)
    lastdaytwomonthsago = lastdaytwomonthsago[:-16]
    start_date_dict = get_sun_data(
        sun_api_boston, utc_tz, local_tz, lastdaytwomonthsago
    )
    monthstart = start_date_dict["sunset"]

    enddate = str(enddate)
    enddate = enddate[:16]
    end_date_dict = get_sun_data(sun_api_boston, utc_tz, local_tz, enddate)
    monthend = end_date_dict["sunrise"]

    target_directory_path_list = []

    for i in directions:
        os.chdir(project_dir + i)
        path = os.getcwd()
        target_directory_name = last_month_name + "-fullmonth"
        target_directory_path = path + "/" + target_directory_name
        target_directory_path_list.append(target_directory_path + "/")
        try:
            target_directory = os.mkdir(target_directory_path)
            logging.info(target_directory_path + " directory created.")
        except FileExistsError:
            logging.error(
                "Directory already exists in " + os.getcwd() + " Nothing created."
            )
        try:
            group_images_between_string_time_infilename(
                path, target_directory_path, monthstart, monthend, local_tz
            )
        except FileNotFoundError:
            logging.error(
                "Directory doesn't exist in " + os.getcwd() + " - no files to copy."
            )
    return target_directory_path_list


def create_timelapses(source_directory_list, filename_list, four_way_identifier=""):
    """create timelapeses from raw image files in grouped directories"""
    today_string = get_today_string()
    input_list = []
    temp_list = []
    for count, i in enumerate(source_directory_list):
        timelapse_cmd = (
            "ffmpeg -framerate "
            + timelapse_config["framerate"]
            + " -pattern_type glob -i "
            + '"'
            + i
            + "*.jpg"
            + '"'
            + " -s:v "
            + timelapse_config["size"]
            + " -c:v libx264 "
            + "-crf 20 "
            + "-pix_fmt "
            + "yuv420p "
            + "-aspect 16:9 "
            + timelapse_dir
            + filename_list[count]
            + "-temp.mp4"
        )
        logging.info(timelapse_cmd)
        try:
            process = subprocess.run([timelapse_cmd], shell=True, check=True, text=True)
            logging.info(
                filename_list[count]
                + " temp timelapse created on "
                + today_string
                + "."
            )
        except subprocess.CalledProcessError:
            logging.error("CalledProcessError")
        temp_list.append(timelapse_dir + filename_list[count] + "-temp.mp4")
        timelapse_cmd = (
            "ffmpeg -i "
            + temp_list[count]
            + ' -filter_complex "[0]trim=0:2[hold];[0][hold]concat[extended];[extended][0]overlay" '
            + timelapse_dir
            + filename_list[count]
            + ".mp4"
        )
        logging.info(timelapse_cmd)
        try:
            process = subprocess.run([timelapse_cmd], shell=True, check=True, text=True)
            logging.info(
                filename_list[count]
                + " final timelapse created on "
                + today_string
                + "."
            )
        except subprocess.CalledProcessError:
            logging.error("CalledProcessError")
        input_list.append(timelapse_dir + filename_list[count] + ".mp4")
    for count, i in enumerate(temp_list):
        try:
            os.remove(temp_list[count])
            logging.error(temp_list[count] + " deleted.")
        except FileNotFoundError:
            logging.error(temp_list[count] + " Does not exist.")


def main():
    # get a whole bunch of needed date information e.g. sunrise-sunset api takes dates as strings
    date = datetime.datetime.today()
    week = datetime.datetime.date(date).isocalendar()[1]
    year = datetime.datetime.now().year
    week = str(year) + "-week-" + str(week)

    current_month = datetime.datetime.now().month
    last_month = current_month - 1
    last_month_name = calendar.month_name[last_month]
    last_month_name = last_month_name.lower()

    today_string = get_today_string()
    tomorrow_string = get_tomorrow_string()
    yesterday_string = get_yesterday_string()

    # get sunrise-sunset.org api data for today tomorrow and yesterday
    sun_data_dict_today = get_sun_data(sun_api_boston, utc_tz, local_tz, today_string)
    sun_data_dict_tomorrow = get_sun_data(
        sun_api_boston, utc_tz, local_tz, tomorrow_string
    )
    sun_data_dict_yesterday = get_sun_data(
        sun_api_boston, utc_tz, local_tz, yesterday_string
    )
    sun_string_dict_today = {}

    # setup variables and lists to help with target directories for files and videos
    day_paths = directions
    daylight_target_directories = []

    # create daytime timelapses if the builder is run during the day manually
    if args.processbatch == "daylight" and args.imagesfrom == "yesterday":
        day_paths = [yesterday_string + "-" + x + "-alldaylight" for x in day_paths]
        for i in directions:
            source_directory = image_storage_root_directory + i
            target_directory = project_dir + i
            daylight_target_directory = create_directory(
                target_directory, yesterday_string, "alldaylight"
            )
            daylight_target_directories.append(str(daylight_target_directory))
            group_images_between_string_time_infilename(
                source_directory,
                daylight_target_directory,
                sun_data_dict_yesterday["civil_twilight_begin"],
                sun_data_dict_yesterday["civil_twilight_end"],
                local_tz,
            )
        create_timelapses(daylight_target_directories, day_paths, "-alldaylight")

    # create daylight timelapses if the builder is run after twilight the day of
    if args.processbatch == "daylight" and args.imagesfrom == "today":
        day_paths = [today_string + "-" + x + "-alldaylight" for x in day_paths]
        for i in directions:
            source_directory = image_storage_root_directory + i
            target_directory = project_dir + i
            daylight_target_directory = create_directory(
                target_directory, today_string, "alldaylight"
            )
            daylight_target_directories.append(str(daylight_target_directory))
            group_images_between_string_time_infilename(
                source_directory,
                daylight_target_directory,
                sun_data_dict_today["civil_twilight_begin"],
                sun_data_dict_today["civil_twilight_end"],
                local_tz,
            )
        create_timelapses(daylight_target_directories, day_paths, "-alldaylight")

    night_paths = directions
    darkness_target_directories = []

    # create darkness timelapses for the most recent night
    if (
        args.processbatch == "darkness"
        and args.imagesfrom == "today"
        or args.imagesfrom == "yesterday"
    ):
        night_paths = [today_string + "-" + x + "-alldarkness" for x in night_paths]
        for i in directions:
            source_directory = image_storage_root_directory + i
            target_directory = project_dir + i
            darkness_target_directory = create_directory(
                target_directory, today_string, "alldarkness"
            )
            darkness_target_directories.append(str(darkness_target_directory))

            hour_before_sunset = sun_data_dict_yesterday["sunset"]
            hour_before_sunset -= datetime.timedelta(hours=1)

            hour_after_sunrise = sun_data_dict_today["sunrise"]
            hour_after_sunrise += datetime.timedelta(hours=1)

            group_images_between_string_time_infilename(
                source_directory,
                darkness_target_directory,
                hour_before_sunset,
                hour_after_sunrise,
                local_tz,
            )

        create_timelapses(darkness_target_directories, night_paths, "-alldarkness")

    logging.info("Timelapse build script ran successfully.")


if __name__ == "__main__":
    main()
