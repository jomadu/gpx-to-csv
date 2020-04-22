import gpxpy
import gpxpy.gpx
import pandas as pd
import os
import numpy as np
import math
import xml.etree.ElementTree as et
from dateutil import parser as dtparser
from datetime import datetime
import argparse

FT_PER_DEG_LAT = 362776.87
FT_PER_DEG_LONG = 365165.34
FT_PER_MILE = 5280
SMOOTHING_WINDOW_WIDTH = 5

MAX_DISTANCE_STEP_SIZE = 0.1 * FT_PER_MILE
MAX_SPEED_STEP_SIZE = 10
MAX_GRADE_STEP_SIZE = 40

# Units in ft, miles

def calcMiles(point_1, point_2, dimensions=['lat','lon','ele']):
    quotient = 0.0

    if 'lat' in dimensions:
        quotient += ((point_2["Latitude"] - point_1["Latitude"]) * FT_PER_DEG_LAT) ** 2
    if 'lon' in dimensions:
        quotient += ((point_2["Longitude"] - point_1["Longitude"]) * FT_PER_DEG_LONG) ** 2
    if 'ele' in dimensions:
        quotient += point_2["Elevation"] - point_1["Elevation"]
    
    return math.sqrt(quotient) / FT_PER_MILE

def calcSpeed(point_1, point_2):
    miles = calcMiles(point_1, point_2)
    t_delta = point_2["Timestamp"] - point_1["Timestamp"]
    hours = t_delta.seconds / 3600 + t_delta.microseconds / (100000 * 3600)
    return miles / hours

def calcGrade(point_1, point_2):
    rise_miles = (point_2["Elevation"] - point_1["Elevation"]) / FT_PER_MILE
    dist_miles = calcMiles(point_1, point_2, dimensions=['lat', 'lon'])
    return rise_miles / dist_miles * 100 if dist_miles else 0.0

def parseGPX(f):
    ns = {'tg': 'http://www.topografix.com/GPX/1/1'}

    points = []
    smoothing_sums = {
        "Speed": 0,
        "Grade": 0,
        "Elevation": 0
    }
    speed_rolling_window_sum = 0
    grade_rolling_window_sum = 0

    with open(f, 'r') as gpxfile:
        xtree = et.parse(gpxfile)
        xroot = xtree.getroot()
        for trk_elem in xroot.iterfind("tg:trk", ns):
            for trkseg_elem in trk_elem.iterfind("tg:trkseg", ns):
                for trkpt_elem in trkseg_elem.iterfind("tg:trkpt", ns):
                    lat = float(trkpt_elem.attrib.get("lat"))
                    lon = float(trkpt_elem.attrib.get("lon"))
                    ele = float(trkpt_elem.find("tg:ele", ns).text)
                    t = dtparser.isoparse(trkpt_elem.find("tg:time", ns).text)
                    curr_point = {
                        "Timestamp": t,
                        "Latitude": lat,
                        "Longitude": lon,
                        "Elevation": ele
                    }
                    if len(points) > 0:
                        distance_since_last = calcMiles(points[-1], curr_point)
                        speed = calcSpeed(points[-1], curr_point)
                        grade = calcGrade(points[-1], curr_point)
                        duration_since_last = curr_point["Timestamp"] - points[-1]["Timestamp"]
                        curr_point["Speed"] = speed if abs(speed - points[-1]["Speed"])  < MAX_SPEED_STEP_SIZE else points[-1]["Speed"]
                        curr_point["Grade"] = grade if abs(grade - points[-1]["Grade"]) < MAX_GRADE_STEP_SIZE else points[-1]["Grade"]
                        curr_point["Distance"] = points[-1]["Distance"] + (distance_since_last if distance_since_last < MAX_DISTANCE_STEP_SIZE else points[-1]["Speed"] * duration_since_last)

                    else:
                        curr_point["Distance"] = 0
                        curr_point["Speed"] = 0
                        curr_point["Grade"] = 0
                    if len(points) >= SMOOTHING_WINDOW_WIDTH:
                        for key in smoothing_sums:
                            smoothing_sums[key] -= points[-SMOOTHING_WINDOW_WIDTH][key]
                            smoothing_sums[key] += curr_point[key]
                            curr_point[key + " (Smoothed)"] = smoothing_sums[key] / SMOOTHING_WINDOW_WIDTH
                    else:
                        for key in smoothing_sums:
                            smoothing_sums[key] += curr_point[key]
                            curr_point[key + " (Smoothed)"] = smoothing_sums[key] / (len(points) + 1)

                    points.append(curr_point)
    return points

def main(args):
    # Change directory to current scripts directory
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    input_dir = args.input_dir    
    output_dir = args.output_dir

    # Scan for files in input directory with extension .gpx
    files = []
    for f in os.listdir(input_dir):
        if f.endswith('.gpx'):
            files.append(f)

    # Summarize inputs
    print('----------')
    print('gpx-to-csv')
    print('----------')
    print(' -> input_dir: {}'.format(input_dir))
    print(' -> output_dir: {}'.format(output_dir))
    print(' -> files found: {}'.format(files))
    print('----------')

    # Convert .gpx files
    print('------------------------')
    print('Starting Convertions ...')
    print('------------------------')
    for f in files:
        if f.endswith('.gpx'):
            input_filename = input_dir + '/' + f
            output_filename = output_dir + '/' + os.path.splitext(os.path.basename(f))[0] + '.csv'
            print('converting: {} -> {}'.format(input_filename, output_filename))
            df = pd.DataFrame(parseGPX(input_filename))
            df.to_csv(output_filename, index=False)
    print('------------------------')
    print('Done converting!')
    print('View converted files in output_dir: {}'.format(output_dir))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input-dir", action="store", dest="input_dir", default="input", help="directory from which .gpx files are parsed")
    parser.add_argument("-o", "--output-dir", action="store", dest="output_dir", default="output", help="directory to which .csv file are written")

    args = parser.parse_args()
    main(args)
