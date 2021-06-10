#!/usr/bin/python3

import os
import sys
import subprocess
import requests
import shutil
from datetime import datetime
import cv2
import numpy as np
import logging
import configparser
import argparse
import json

# read in config from config.txt
parser = argparse.ArgumentParser()
parser.add_argument(
    "--config",
    required=True,
    help="filename - dhconfig.txt or bhconfig.txt",
)
args = parser.parse_args()

config = configparser.ConfigParser()

#forces cront to read in file from correct path
config_file = os.path.join(os.path.dirname(__file__), args.config)
config.read(config_file)

# set config variables
image_storage_root_directory = config["directories"]["image_storage_root_directory"]
image_log_location = config["logging"]["image_log_location"]
image_url = config["api_urls"]["image_url"]
slackhook = config["slack"]["slackhook"]
slackheaders = config["slack"]["slackheaders"]

# convert slack headers to dict
slackheaders = json.loads(slackheaders)

# Logging Configuration
logging.basicConfig(
    filename=image_log_location,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)

# Timestamp for filenmaes
timestamp = datetime.now()
timestamp = timestamp.strftime("%Y%m%d_%H-%M")
process = ""
# Set filename
filename = timestamp + ".fullimage.jpg"

def rotate_image(image, angle):
    """rotate image where needed"""
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
    return result

def get_image():
    """grab image from url"""
    os.chdir(image_storage_root_directory)
    # Open the url image, set stream to True, this will return the stream content.
    try:
        r = requests.get(image_url, stream=True)
            # Check if the image was retrieved successfully
        if r.status_code == 200:
            # Set decode_content value to True, otherwise the downloaded image file's size will be zero.
            r.raw.decode_content = True
            # Open a local file with wb ( write binary ) permission.
            with open(filename, "wb") as f:
                shutil.copyfileobj(r.raw, f)

            logging.info("Image Sucessfully Downloaded: " + filename)
        else:
            errormsg = "Image Was Not Downloaded @" + timestamp
            logging.error(errormsg)
            slackjson = {"text": errormsg}
            r = requests.post(slackhook, json=slackjson, headers=slackheaders)
            if r.status_code == 200:
                logging.info("Slack Errror Message Sent.")
            else:
                logging.error("Slack Notification Failed")
    except requests.exceptions.ConnectionError:
        logging.info("Connection Error. Internet likely down.")
        sys.exit()
    return filename
       
def process_valid_image(config):
    """validate if image is a properly downloaded jpeg"""  
    for attempt in range(3):
        try:
            filename = get_image()
            jpeginfocmd = "jpeginfo -c " + filename
            process = subprocess.run(jpeginfocmd, shell=True, check=True, text=True, capture_output=True)
            logging.info("Image Passed Check On Attempt " + str(attempt))
            process_image(config, filename)
        except subprocess.CalledProcessError:
            continue
        else:
            break
    else:
        errormsg = "Image Failed Check After All Attempts " + args.config + " " + filename
        logging.info(errormsg)
        old_dir = image_storage_root_directory + filename
        logging.info("Original file location " + old_dir)
        new_dir = image_storage_root_directory + "badimages/" + filename
        logging.info("New file location " + new_dir)
        os.rename(old_dir, new_dir)
        slackjson = {"text": errormsg}
        r = requests.post(slackhook, json=slackjson, headers=slackheaders)


def process_image(config, filename):
    """crop and process image"""
    if args.config == "dhconfig.txt":
        img = cv2.imread(filename)
        cropped_img = img[1340:2340, 0:7360]
        south_img1 = cropped_img[0:1000, 0:1640]
        south_img2 = cropped_img[0:1000, 7160:7360]
        south_img = np.concatenate((south_img2, south_img1), axis=1)
        west_img = cropped_img[0:1000, 1640:3480]
        north_img = cropped_img[0:1000, 3480:5320]
        east_img = cropped_img[0:1000, 5320:7160]

    elif args.config == "bhconfig.txt":
        img = cv2.imread(filename)
        cropped_img = img[1350:2410, 0:7184]
        north_img1 = cropped_img[0:1000, 0:200]
        north_img2 = cropped_img[0:1000, 5588:7184]
        north_img = np.concatenate((north_img2, north_img1), axis=1)
        north_img = rotate_image(north_img, 2.75)
        north_img = north_img[50:950, 25:1771]
        east_img = cropped_img[0:1000, 200:1996]
        east_img = rotate_image(east_img, 2.5)
        east_img = east_img[50:950, 25:1771]
        south_img = cropped_img[0:1000, 1996:3792]
        south_img = rotate_image(south_img, -3.0)
        south_img = south_img[50:950, 25:1771]
        west_img = cropped_img[0:1000, 3792:5588]
        west_img = rotate_image(west_img, -3.0)
        west_img = west_img[50:950, 25:1771]

    camera_views = {
        "south": south_img,
        "west": west_img,
        "north": north_img,
        "east": east_img,
    }

    for key in camera_views:
        name = filename[:-13] + key + ".jpg"
        os.chdir(image_storage_root_directory + key)
        cv2.imwrite(name, camera_views[key])
        logging.info("Image File Written: " + name)

    os.remove(image_storage_root_directory + filename)
    logging.info("Image Sucessfully Processed and Original Removed " + filename)

def main():
    config = args.config
    process_valid_image(config)
if __name__ == "__main__":
    main()
