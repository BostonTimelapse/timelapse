#!/usr/bin/python3

import os
import subprocess
import datetime
import pathlib
import time
import configparser
import argparse
import json
import logging
import calendar
from dateutil import tz
from random import randrange
import glob
import requests
import tweepy
from google.cloud import storage

# parse arguments to make this script more flexible
parser = argparse.ArgumentParser()
parser.add_argument(
    "--config", required=True, help="filename - dhconfig.txt or bhconfig.txt"
)
parser.add_argument("--tweets", help="bhtweets.txt or dhtweets.txt")
parser.add_argument("--adhoctweet", help="used to do a adhoc manual tweet")
parser.add_argument("--adhocinsta", help="used to do a adhoc manual post on instagram")
parser.add_argument(
    "--imagepath", help="path to image to do an adhoc manual tweet or instapost"
)
parser.add_argument("--filename", help="instagram needs filename for post")
args = parser.parse_args()

config_files = []
config = configparser.ConfigParser()
# this is needed so cron can find the config file
config_file1 = os.path.join(os.path.dirname(__file__), args.config)
config_files.append(config_file1)
if args.tweets is not None:
    # this is needed so cron can find the config file
    config_file2 = os.path.join(os.path.dirname(__file__), args.tweets)
    config_files.append(config_file2)
config.read(config_files)

# load config variables.... this could be cleaned up.
log_dir = config["directories"]["log_dir"]
image_dir = config["directories"]["project_dir"]
timelapse_dir = config["directories"]["timelapse_dir"]
sun_api_boston = config["api_urls"]["sun_api_boston"]
api_key = config["twitter"]["api_key"]
api_secret = config["twitter"]["api_secret"]
bearer_token = config["twitter"]["bearer_token"]
access_token = config["twitter"]["access_token"]
access_token_secret = config["twitter"]["access_token_secret"]
twitter_log_location = config["logging"]["twitter_log_location"]
instagram_access_token = config["instagram"]["access_token"]
instagram_business_account = config["instagram"]["instagram_business_account"]
monument_location_id = config["instagram"]["monument_location_id"]
gcp_bucket = config["gcp"]["bucket"]
gcp_folder = config["gcp"]["folder"]
gcp_base_url = config["gcp"]["base_url"]

# logging config
logging.basicConfig(
    filename=twitter_log_location,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)
# date stuff
date = datetime.datetime.today()
month = datetime.datetime.now().month
year = datetime.datetime.now().year
day = datetime.datetime.now().day
c = calendar.Calendar(firstweekday=calendar.MONDAY)
monthcal = c.monthdatescalendar(year, month)

utc_tz = tz.gettz("UTC")
local_tz = tz.gettz("America/New_York")
today = datetime.datetime.today()

daylight_cronrun_start_time = today.replace(hour=17, minute=00, second=00).astimezone(
    local_tz
)
daylight_cronrun_end_time = today.replace(hour=23, minute=59, second=00).astimezone(
    local_tz
)

darkness_cronrun_start_time = today.replace(hour=6, minute=00, second=00).astimezone(
    local_tz
)
darkness_cronrun_end_time = today.replace(hour=11, minute=59, second=00).astimezone(
    local_tz
)
random_image_tweet_time = today.replace(hour=12, minute=00).astimezone(local_tz)

monument_lat = float(config["twitter"]["monument_lat"])
monument_long = float(config["twitter"]["monument_long"])

# create helper lists
directions = ["north", "east", "south", "west"]
string_days = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]

# get google storage client and bucket
if args.adhoctweet is None:
    client = storage.Client()
    bucket = client.get_bucket(gcp_bucket)

if args.adhoctweet is None and args.adhocinsta is None:
    # f = open(
    #     log_dir + "youtubeids.json",
    # )
    # youtube_video_dict = json.load(f)
    # f.close()

    f = open(
        log_dir + "vimeolinks.json",
    )
    vimeo_video_dict = json.load(f)
    f.close()
    f = open(
        log_dir + "videodict.json",
    )
    video_dict = json.load(f)
    f.close()


def get_today_string():
    """returns today as a string"""
    today = datetime.datetime.today()
    today = str(today)
    today = today[:-16]
    return today


def get_yesterday_string():
    """returns yesterday as a string"""
    yesterday = datetime.datetime.today()
    yesterday -= datetime.timedelta(days=1)
    yesterday = str(yesterday)
    yesterday = yesterday[:-16]
    return yesterday


def get_astro_event_string_time(event):
    """returns astronomical event as a string"""
    r = requests.get(sun_api_boston + "&date=" + get_yesterday_string())
    jsonResponse = r.json()
    sun_data_dict = jsonResponse["results"]
    event_time = sun_data_dict[event]
    event_time = datetime.datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%S+00:00")
    event_time = event_time.replace(tzinfo=utc_tz)
    event_time = event_time.astimezone(local_tz)
    event_time = event_time.strftime("%Y%m%d_%H-%M")
    return event_time


def make_day_lists():
    """build list of lists where each list index corresponds to the day of the week
    and each element in the lists corresponds to the first, second.. etc time that day occurs in the month"""
    MONDAY = []
    TUESDAY = []
    WEDNESDAY = []
    THURSDAY = []
    FRIDAY = []
    SATURDAY = []
    SUNDAY = []
    week_list = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]

    count = 0
    for i in string_days:
        occurences_in_month = len(
            [
                1
                for i in calendar.monthcalendar(
                    datetime.datetime.now().year, datetime.datetime.now().month
                )
                if i[count] != 0
            ]
        )
        for x in range(occurences_in_month):
            day = [
                day
                for week in monthcal
                for day in week
                if day.weekday() == getattr(calendar, i) and day.month == month
            ][x]
            week_list[count].append(day)
        count += 1
    return week_list


def get_day_of_month(day_int):
    """takes current date and gets the occurence of that day of the week in the month.
    e.g. 2nd monday of may, 5th friday of august"""
    now = datetime.datetime.now()
    day_list = make_day_lists()
    now = datetime.date(now.year, now.month, now.day)
    occurence_in_month = day_list[day_int].index(now)
    logging.info("Day's occurence in month = " + str(occurence_in_month))
    return occurence_in_month


def get_daily_run_number():
    """determines if the upload is a daylight timelapse or darkness
    timelapse in order to compose tweets accordingly"""
    time = date.replace(tzinfo=local_tz)
    if time >= darkness_cronrun_start_time and time <= darkness_cronrun_end_time:
        dailytweetrun = 1
    elif time >= daylight_cronrun_start_time and time <= daylight_cronrun_end_time:
        dailytweetrun = 2
    elif time.hour == random_image_tweet_time.hour:
        dailytweetrun = 3
    else:
        dailytweetrun = 0
        logging.info("not in the range of times to tweet")
    logging.info("Daily tweet run number = " + str(dailytweetrun))
    return dailytweetrun


def get_tweet_image(dailytweetrun):
    """gets first image from randomly chosen direction for daylight or darkness"""
    today_string = get_today_string()
    yesterday_string = get_yesterday_string()
    directions = ["north", "east", "south", "west"]
    tweet_image = ""
    random_index = randrange(len(directions))
    rand_direction = directions[random_index]
    if dailytweetrun == 1 and args.config == "dhconfig.txt":
        image_location = (
            image_dir + rand_direction + "/" + today_string + "/" + "alldarkness"
        )
        sunset = get_astro_event_string_time("sunset")
        tweet_image = image_location + "/" + sunset + "." + rand_direction + ".jpg"
        logging.info("run 1 dhconfig " + tweet_image)
    elif dailytweetrun == 1 and args.config == "bhconfig.txt":
        image_location = image_dir + "south/" + today_string + "/" + "alldarkness"
        sunset = get_astro_event_string_time("sunset")
        tweet_image = image_location + "/" + sunset + ".south.jpg"
        logging.info("run 1 bhconfig" + tweet_image)
    elif dailytweetrun == 2:
        random_index = randrange(len(directions))
        image_location = (
            image_dir
            + directions[random_index]
            + "/"
            + today_string
            + "/"
            + "alldaylight"
        )
        list_of_files = glob.glob(
            image_location + "/*"
        )  # * means all if need specific format then *.csv
        random_index = randrange(len(list_of_files))
        tweet_image = list_of_files[random_index]
    elif dailytweetrun == 3:
        random_index = randrange(len(directions))
        image_location = (
            image_dir
            + directions[random_index]
            + "/"
            + yesterday_string
            + "/"
            + "alldaylight"
        )
        list_of_files = glob.glob(image_location + "/*")
        random_index = randrange(len(list_of_files))
        tweet_image = list_of_files[random_index]
    logging.info("Random image from time window grabbed for tweet. " + tweet_image)
    return tweet_image


def get_random_timelapse_clip():
    # get random timelapse clip
    timelapse_list = []
    count = 0
    now = datetime.datetime.now()
    yesterday = now - datetime.timedelta(days=1)
    for file in os.listdir(timelapse_dir):
        path = timelapse_dir + file
        mtime = os.path.getmtime(path)
        mtime = datetime.datetime.fromtimestamp(mtime)
        if (
            args.config == "dhconfig.txt"
            and file.endswith(".mp4")
            and mtime > yesterday
            and "fourway" not in file
        ):
            timelapse_list.append(file)
        elif (
            args.config == "bhconfig.txt"
            and file.endswith(".mp4")
            and mtime > yesterday
            and "west" not in file
            and "north" not in file
            and "fourway" not in file
        ):
            timelapse_list.append(file)
        else:
            continue
    random_index = randrange(len(timelapse_list))
    random_timelapse = timelapse_list[random_index]

    length_cmd = (
        "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "
        + timelapse_dir
        + random_timelapse
    )

    try:
        process = subprocess.run(
            [length_cmd], shell=True, check=True, text=True, capture_output=True
        )
        length = int(float(process.stdout))
        logging.info(random_timelapse + " is " + str(length) + " seconds long.")
    except subprocess.CalledProcessError:
        logging.error("CalledProcessError " + length_cmd)

    clip_length = 10
    random_start = randrange(length - clip_length)

    clip_name = random_timelapse[:-3] + "twitter.mp4"
    timelapse_cmd = (
        "ffmpeg -ss "
        + str(random_start)
        + " -i "
        + timelapse_dir
        + random_timelapse
        + " -c copy -t "
        + str(clip_length)
        + " "
        + timelapse_dir
        + clip_name
    )
    logging.info(timelapse_cmd)
    try:
        process = subprocess.run([timelapse_cmd], shell=True, check=True, text=True)
        logging.info(
            "Timelapse clip created from " + random_timelapse + " for random clip post"
        )
    except subprocess.CalledProcessError:
        logging.error("CalledProcessError " + timelapse_cmd)
    return clip_name


def get_tweet_copy(dailytweetrun, link):
    """pulls copy from config file - including defaults"""
    run = "MORNING"
    default_copy = ""
    if dailytweetrun == 1:
        default_copy = config["darkness"]["default"]
        run = "MORNING"
    elif dailytweetrun == 2:
        default_copy = config["daylight"]["default"]
        run = "NIGHT"
    day_int = datetime.datetime.today().weekday()
    day_occurence = get_day_of_month(day_int)
    RUNNAME = string_days[day_int] + run
    day_of_week_copy = config[RUNNAME][str(day_occurence)]
    if len(day_of_week_copy) == 0 and dailytweetrun != 3 or 0:
        tweet_copy = default_copy + " " + link
    elif dailytweetrun == 3:
        tweet_copy = config["randomimage"]["default"]
    else:
        tweet_copy = day_of_week_copy + " " + link
    logging.info(tweet_copy)
    return tweet_copy


def get_youtube_link(dailytweetrun):
    """grabs links from youtub uploads - may never use again"""
    youbtube_link = "https://youtu.be/"
    link = ""
    for key in youtube_video_dict:
        if dailytweetrun == 1 and "darkness" in key:
            link = youbtube_link + youtube_video_dict[key]
        if dailytweetrun == 2 and "daylight" in key:
            link = youbtube_link + youtube_video_dict[key]
    logging.info("Video link to be tweeted. " + link)
    return link


def get_vimeo_link(dailytweetrun):
    """grabs links to uploaded vimeo videos"""
    link = ""
    for key in vimeo_video_dict:
        if dailytweetrun == 1 and "darkness" in key:
            link = vimeo_video_dict[key]
        if dailytweetrun == 2 and "daylight" in key:
            link = vimeo_video_dict[key]
    logging.info("Video link to be tweeted. " + link)
    return link


def instagram_image_post(image_url, caption):
    """Post image to instagram"""
    post_url = "https://graph.facebook.com/v10.0/{}/media".format(
        instagram_business_account
    )
    payload = {
        "image_url": image_url,
        "caption": caption,
        "location_id": monument_location_id,
        "access_token": instagram_access_token,
    }
    r = requests.post(post_url, data=payload)
    result = json.loads(r.text)
    logging.info(result)
    if "id" in result:
        creation_id = result["id"]
        second_url = "https://graph.facebook.com/v10.0/{}/media_publish".format(
            instagram_business_account
        )
        second_payload = {
            "creation_id": creation_id,
            "access_token": instagram_access_token,
        }
        r = requests.post(second_url, data=second_payload)
        logging.info("Posted " + image_url + " to instagram " + r.text)
    else:
        logging.info("Instagram photo post failed.")


def get_instagram_image_url(local_image_path):
    """get url for instagram image upload"""
    image_dict = {}
    if "east.jpg" in local_image_path or "west.jpg" in local_image_path:
        image_file = local_image_path[-23:]
        blob = bucket.blob(gcp_folder + "/" + image_file)
        blob.upload_from_filename(filename=local_image_path)
        blob_url = gcp_base_url + gcp_bucket + "/" + gcp_folder + "/" + image_file
        image_dict[image_file] = blob_url
        time.sleep(1)
    elif "south.jpg" in local_image_path or "north.jpg" in local_image_path:
        image_file = local_image_path[-24:]
        blob = bucket.blob(gcp_folder + "/" + image_file)
        blob.upload_from_filename(filename=local_image_path)
        blob_url = gcp_base_url + gcp_bucket + "/" + gcp_folder + "/" + image_file
        image_dict[image_file] = blob_url
        time.sleep(1)
    else:
        logging.info("cant get image url something odd going on " + local_image_path)

    return image_dict


def get_instagram_video_url(filename, path):
    """grab url for instagram video upload"""
    filename = filename[:-3] + "instagram.mp4"
    path = path[:-3] + "instagram.mp4"
    blob = bucket.blob(gcp_folder + "/" + filename)
    blob.upload_from_filename(filename=path)
    blob_url = gcp_base_url + gcp_bucket + "/" + gcp_folder + "/" + filename
    time.sleep(1)
    return blob_url


def get_adhoc_instagram_video_url(filename, path):
    """get url for adhoc instagram video upload"""
    blob = bucket.blob(gcp_folder + "/" + filename)
    blob.upload_from_filename(filename=path)
    blob_url = gcp_base_url + gcp_bucket + "/" + gcp_folder + "/" + filename
    time.sleep(1)
    return blob_url


def check_upload_status(creation_id):
    """check if video has been uploaded. this is recursive mofos"""
    url = (
        "https://graph.facebook.com/"
        + creation_id
        + "?fields=status_code&access_token="
        + instagram_access_token
    )
    r = requests.get(url)
    result = json.loads(r.text)
    logging.info(result)
    if result["status_code"] == "ERROR":
        logging.info(
            "Instagram video post failed " + result["status_code"] + " " + r.text
        )
    elif result["status_code"] == "IN_PROGRESS":
        time.sleep(5)
        check_upload_status(creation_id)
    elif result["status_code"] == "FINISHED":
        pass
    else:
        logging.info("Instagram media post failed.")


def instagram_video_post(video_url, caption):
    """post video to instagram"""
    post_url = "https://graph.facebook.com/v10.0/{}/media".format(
        instagram_business_account
    )
    payload = {
        "video_url": video_url,
        "caption": caption,
        "media_type": "VIDEO",
        "location_id": monument_location_id,
        "access_token": instagram_access_token,
    }
    r = requests.post(post_url, data=payload)
    result = json.loads(r.text)
    logging.info(result)
    if "id" in result:
        creation_id = result["id"]
        time.sleep(2)
        check_upload_status(creation_id)
        url = "https://graph.facebook.com/v10.0/{}/media_publish".format(
            instagram_business_account
        )
        payload = {"creation_id": creation_id, "access_token": instagram_access_token}
        r = requests.post(url, data=payload)
        logging.info("Posted " + video_url + " to instagram " + r.text)
    else:
        logging.info("Instagram video post failed.")


def create_insta_video_dict(dailyinstarun, videodict):
    """creates dict of videos to be posted to instagram"""
    insta_video_dict = {}
    for key in video_dict:
        if dailyinstarun == 1 and "east" in key:
            video_path = video_dict[key]
            insta_video_dict[key] = video_path
        elif dailyinstarun == 2 and args.config == "dhconfig.txt" and "west" in key:
            video_path = video_dict[key]
            insta_video_dict[key] = video_path
        elif dailyinstarun == 2 and args.config == "bhconfig.txt" and "south" in key:
            video_path = video_dict[key]
            insta_video_dict[key] = video_path
    return insta_video_dict


def create_twitter_video_dict(videodict):
    """creates dict of videos to be posted to twitter"""
    twitter_video_dict = {}
    for key in video_dict:
        if "fourway" in key:
            video_path = video_dict[key]
            twitter_video_dict[key] = video_path
    return twitter_video_dict


def timelapse_clip_builder(video_dict, videosuffix):
    """makes a clip of a timelapse"""
    for key in video_dict:
        timelapse_cmd = (
            "ffmpeg -sseof -12 -i "
            + video_dict[key]
            + " -s:v hd1080 "
            + video_dict[key][:-3]
            + videosuffix
        )
        logging.info(timelapse_cmd)
        try:
            process = subprocess.run([timelapse_cmd], shell=True, check=True, text=True)
            logging.info("Timelapse clip created " + key)
        except subprocess.CalledProcessError:
            logging.error("CalledProcessError " + timelapse_cmd)
    return video_dict


def get_insta_copy(dailyinstarun):
    """grabs copy for instgram post"""
    default_copy = ""
    if dailyinstarun == 1:
        default_copy = config["instacopy"]["sunrise"]
    elif dailyinstarun == 2:
        default_copy = config["instacopy"]["sunset"]
    logging.info(default_copy)
    return default_copy


def main():
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(api_key, api_secret)
    auth.set_access_token(access_token, access_token_secret)

    # Create API object
    api = tweepy.API(auth)
    logging.info(api)

    # get daily tweet run number to determine behavior
    dailytweetrun = get_daily_run_number()

    if args.adhoctweet is not None:
        tweet_copy = args.adhoctweet
        if args.imagepath is not None:
            image = args.imagepath
            media = api.media_upload(image)
            post_result = api.update_status(
                status=tweet_copy,
                media_ids=[media.media_id],
                lat=monument_lat,
                long=monument_long,
            )
        else:
            post_result = api.update_status(
                status=tweet_copy, lat=monument_lat, long=monument_long
            )
            logging.info(post_result.text)

    elif args.adhocinsta is not None:
        insta_copy = args.adhocinsta
        if args.imagepath is None:
            sys.exit("Hey moron! Don't post to the 'gram' without a pic!")
        else:
            image_path = args.imagepath
            image_url = get_adhoc_instagram_video_url(args.filename, image_path)
            instagram_video_post(image_url, insta_copy)
            bucket.delete_blob(gcp_folder + "/" + args.filename)

    elif dailytweetrun == 3:
        insta_copy = get_tweet_copy(dailytweetrun, "")
        timelapse_clip = get_random_timelapse_clip()
        timelapse_clip_path = timelapse_dir + timelapse_clip
        media = api.media_upload(timelapse_clip_path)
        post_result = api.update_status(
            status=insta_copy,
            media_ids=[media.media_id],
            lat=monument_lat,
            long=monument_long,
        )
        logging.info(insta_copy + " " + timelapse_clip)
        video_url = get_adhoc_instagram_video_url(timelapse_clip, timelapse_clip_path)
        instagram_video_post(video_url, insta_copy)
        bucket.delete_blob(gcp_folder + "/" + timelapse_clip)

    else:
        vimeo_link = get_vimeo_link(dailytweetrun)
        tweet_copy = get_tweet_copy(dailytweetrun, vimeo_link)
        logging.info(tweet_copy)

        insta_video_dict = create_insta_video_dict(dailytweetrun, video_dict)
        logging.info("instagram video " + str(insta_video_dict))
        twitter_video_dict = create_twitter_video_dict(video_dict)
        logging.info("twitter video " + str(twitter_video_dict))
        timelapse_clip_builder(insta_video_dict, "instagram.mp4")
        timelapse_clip_builder(twitter_video_dict, "twitter.mp4")
        for key in twitter_video_dict:
            filename = key[:-3] + "twitter.mp4"
            filepath = twitter_video_dict[key][:-3] + "twitter.mp4"
            media = api.media_upload(filepath)
            post_result = api.update_status(
                status=tweet_copy,
                media_ids=[media.media_id],
                lat=monument_lat,
                long=monument_long,
            )
            logging.info(post_result.text)
            os.remove(filepath)
        for key in insta_video_dict:
            filename = key[:-3] + "instagram.mp4"
            video_url = get_instagram_video_url(key, insta_video_dict[key])
            instacopy = get_insta_copy(get_daily_run_number())
            instagram_video_post(video_url, instacopy)
            try:
                bucket.delete_blob(gcp_folder + "/" + filename)
                os.remove(filepath)
            except NotFound:
                logging.info("Google API exception raised")


if __name__ == "__main__":
    main()
