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
ROLLING_WINDOW_WIDTH = 20
input = []

# Units in ft, miles

ns = {'tg': 'http://www.topografix.com/GPX/1/1'}

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
    hours = (point_2["Timestamp"] - point_1["Timestamp"]).seconds / 3600
    return miles / hours

def calcGrade(point_1, point_2):
    rise_miles = (point_2["Elevation"] - point_1["Elevation"]) / FT_PER_MILE
    dist_miles = calcMiles(point_1, point_2, dimensions=['lat', 'lon'])
    return rise_miles / dist_miles * 100 if dist_miles else 0.0

def parseGPX(f):
    points = []
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
                        curr_point["Distance"] = points[-1]["Distance"] + calcMiles(points[-1], curr_point)
                        curr_point["Speed"] = calcSpeed(points[-1], curr_point)
                        curr_point["Grade"] = calcGrade(points[-1], curr_point)
                        start_time = points[0]["Timestamp"]
                        curr_point["Duration"] = curr_point["Timestamp"] - start_time
                    else:
                        curr_point["Distance"] = 0
                        curr_point["Speed"] = 0
                        curr_point["Grade"] = 0
                        start_time = curr_point["Timestamp"]
                        curr_point["Duration"] = curr_point["Timestamp"] - start_time

                    if len(points) >= ROLLING_WINDOW_WIDTH:
                        speed_rolling_window_sum -= points[-ROLLING_WINDOW_WIDTH]["Speed"]
                        speed_rolling_window_sum += curr_point["Speed"]
                        curr_point["Speed (Window Avg)"] = speed_rolling_window_sum / ROLLING_WINDOW_WIDTH

                        grade_rolling_window_sum -= points[-ROLLING_WINDOW_WIDTH]["Grade"]
                        grade_rolling_window_sum += curr_point["Grade"]
                        curr_point["Grade (Window Avg)"] = grade_rolling_window_sum / ROLLING_WINDOW_WIDTH
                    else:
                        speed_rolling_window_sum += curr_point["Speed"]
                        curr_point["Speed (Window Avg)"] = speed_rolling_window_sum / (len(points) + 1)

                        grade_rolling_window_sum += curr_point["Grade"]
                        curr_point["Grade (Window Avg)"] = grade_rolling_window_sum / (len(points) + 1)

                    points.append(curr_point)
    return points

def main(args):
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    input_dir = args.input_dir    
    output_dir = args.output_dir

    files = []
    for f in os.listdir(input_dir):
        if f.endswith('.gpx'):
            files.append(f)

    print('----------')
    print('gpx-to-csv')
    print('----------')
    print(' -> input_dir: {}'.format(input_dir))
    print(' -> output_dir: {}'.format(output_dir))
    print(' -> files found: {}'.format(files))
    print('----------')

    
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
