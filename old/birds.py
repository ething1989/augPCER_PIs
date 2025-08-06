import os
import sys
import json
import datetime
import csv
import sounddevice as sd
import operator
import numpy as np

import colorsys
import sys
import ST7735

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    print("Can't import LTR559")
    import ltr559

from bme280 import BME280
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging

from juara_credentials import conn

def sql_insert(dict):
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO data "
            keys_list = [f"`{x}`" for x in dict.keys()]
            values_list = [f"{x}" for x in dict.values()]
            sql += "(" + ",".join(keys_list) + ")" +  " VALUES " + "(" + ",".join(values_list) + ");"
            cursor.execute(sql)
            print("Successfully Inserted SQL Query")
        conn.commit()
    except:
        print("SQL Insert Failed")
        pass #conn.close()

external_sensors = False
try:
    import board
    import adafruit_htu31d
    i2c = board.I2C()
    htu = adafruit_htu31d.HTU31D(i2c)
    external_sensors = True
except:
    print("No external sensors")

import config as cfg

def loadCodes():

    with open(cfg.CODES_FILE, 'r') as cfile:
        codes = json.load(cfile)

    return codes

def loadLabels(labels_file):

    labels = []
    with open(labels_file, 'r') as lfile:
        for line in lfile.readlines():
            labels.append(line.replace('\n', ''))

    return labels

def loadSpeciesList(fpath):

    slist = []
    if not fpath == None:
        with open(fpath, 'r') as sfile:
            for line in sfile.readlines():
                species = line.replace('\r', '').replace('\n', '')
                slist.append(species)

    return slist

# location info
# CA is default

# Pantanal
cfg.LATITUDE = -17.1026
cfg.LONGITUDE = -56.9434
# Xingu
# cfg.LATITUDE = -12.3519
# cfg.LONGITUDE = -53.2092
cfg.WEEK = 33
cfg.LOCATION_FILTER_THRESHOLD = 0.03

cfg.LATITUDE = -1
cfg.LONGITUDE = -1
cfg.SPECIES_LIST_FILE = 'pantanal_species_list.txt'

cfg.CODES = loadCodes()
cfg.LABELS = loadLabels(cfg.LABELS_FILE)
cfg.SPECIES_LIST = loadSpeciesList(cfg.SPECIES_LIST_FILE)

bme280 = BME280()

st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
#st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

#print(f"display dimensions: {WIDTH}x{HEIGHT}")

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size_small = 10
font_size_large = 20
font = ImageFont.truetype(UserFont, font_size_large)
smallfont = ImageFont.truetype(UserFont, font_size_small)
x_offset = 2
y_offset = 2

message = ""

def display_print( message, coords=(0, 0), font=smallfont, fill=(255, 255, 255)):
        x = x_offset + int(WIDTH * coords[0])
        y = y_offset + int(HEIGHT * coords[1])
        draw.text((x, y), message, font=font, fill=fill)

print("Starting")
model_version = cfg.MODEL_PATH.split('/')[1]
draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
display_print(f"Starting...{model_version}", coords=(.1, .1), font=font)
display_print(f"Using {len(cfg.SPECIES_LIST)} species", coords=(0, .6), font=smallfont)
display_print(f"{cfg.SPECIES_LIST_FILE}", coords=(0, .8), font=smallfont)
st7735.display(img)

# Initialize display
st7735.begin()

# The position of the top bar
top_pos = 25

def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])

def get_weather():
	cpu_temp = get_cpu_temperature()
	temp = bme280.get_temperature()
	pressure = bme280.get_pressure()
	humidity = bme280.get_humidity()
	lux = ltr559.get_lux()
	temp -= (cpu_temp - temp) / 2.25
	if external_sensors:
		temp, humidity = htu.measurements
	return [f"{temp:.1f}C", f"{pressure:.0f}hPa", f"{humidity:.0f}%", f"{lux:.0f}lx"], [temp, pressure, humidity, lux]

import model

#draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
#display_print(f"Model Loaded", coords=(.1, .3), font=font)
#st7735.display(img)

#def display_print( message, coords=(0, 0), font=smallfont, fill=(255, 255, 255)):
#	x = x_offset + int(WIDTH * coords[0])
#	y = y_offset + int(HEIGHT * coords[1])
#	draw.text((x, y), message, font=font, fill=fill)


cfg.TFLITE_THREADS = 2
# cfg.CPU_THREADS = 4
SAMPLERATE = 48000
sd.default.samplerate = SAMPLERATE
sd.default.channels = 1

def loadCodes():

    with open(cfg.CODES_FILE, 'r') as cfile:
        codes = json.load(cfile)

    return codes

def loadLabels(labels_file):

    labels = []
    with open(labels_file, 'r') as lfile:
        for line in lfile.readlines():
            labels.append(line.replace('\n', ''))    

    return labels

cfg.CODES = loadCodes()
cfg.LABELS = loadLabels(cfg.LABELS_FILE)

cfg.MIN_CONFIDENCE = 0.05

def get_db(data, min_thresh=80):
	segments = data.reshape(-1, int(SAMPLERATE*.25))
	maxes = np.zeros(len(segments))
	for i, segment in enumerate(segments):
		max_amp = max(np.abs(segment))
		maxes[i] = max_amp
	av_max_amp = np.mean(maxes[1:])
	max_db = 20*np.log10(max(maxes[1:])) + min_thresh
	db = 20*np.log10(av_max_amp) + min_thresh
	return min(min_thresh, db), min(min_thresh, max_db)





#print("Starting")

#draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
#display_print(f"Starting", coords=(.3, .4), font=font)
#st7735.display(img)

csv_file_name = str(datetime.datetime.now().strftime("%Y-%m-%d"))

time_interval = cfg.LOG_INTERVAL

data_dict_init = {}
data_dict_init["Time"] = 0
data_dict_init["Temp"] = 0
data_dict_init["Pressure"] = 0
data_dict_init["Humidity"] = 0
data_dict_init["Light"] = 0
for species in cfg.SPECIES_LIST:
	data_dict_init[species] = 0

data_dict = data_dict_init.copy()
header_row = list(data_dict.keys())
with open(f"record-{csv_file_name}.csv", "w") as f:
	writer = csv.writer(f)
	writer.writerow(header_row)
	f.close()

max_dbs = [0]*5
new_data = False
step_counter = 0
weather_arr = np.zeros((time_interval, 4))
sql_dict = {}
try:
	while True:
		start_time = datetime.datetime.now()
		rec_data = sd.rec(SAMPLERATE*3, device="adau7002")
		if new_data:
			step_counter += 1
			new_data = False

			weather_data, float_weather_data = get_weather()
			weather_arr[((step_counter-1) % time_interval)] = float_weather_data

			start_time = datetime.datetime.now()
			data -= np.mean(data)
			data *= 2 # min(np.max(data), 30)
			prediction = model.predict([data])
			if cfg.APPLY_SIGMOID:
					prediction = model.flat_sigmoid(np.array(prediction), sensitivity=-cfg.SIGMOID_SENSITIVITY)
			p_labels = dict(zip(cfg.LABELS, prediction[0]))
			p_sorted =  sorted(p_labels.items(), key=operator.itemgetter(1), reverse=True)
			print(p_sorted[0:5])
			end_time = datetime.datetime.now()
			print(f"Inference time: {end_time-start_time}")
			
			db, max_db = get_db(data)
			db -= 20
			max_db -= 20
			max_dbs = max_dbs[1:] + [max_db]
			
			draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
			for i in range(4):
				display_print(weather_data[i], coords=(0, i/5))
			for i in range(5):
				flname = p_sorted[i][0]
				name = p_sorted[i][0].split("_")[1]
				prob = p_sorted[i][1]
				if prob > cfg.MIN_CONFIDENCE and flname in cfg.CODES and (flname in cfg.SPECIES_LIST or len(cfg.SPECIES_LIST) == 0):
					display_print(f"{prob:.0%} {name}", coords=(.27, i/5))
					#if name in data_dict:
					data_dict[flname] += 1
					#else:
					#	data_dict[name] = 1
					if name in sql_dict:
						sql_dict[name] += 1
					else:
						sql_dict[name] = 1
			draw.polygon([(0,HEIGHT-1), (.26*WIDTH, HEIGHT-1), (.26*WIDTH, .8*HEIGHT), (0, .8*HEIGHT)], outline=(255,255,255), fill=(0,0,0))
			draw.rectangle((1, .8*HEIGHT+1, .26*WIDTH*min((db)/60,1) - 1, HEIGHT - 2), outline=(255,0,0), fill=(255,0,0))
			draw.rectangle((1 + max(max_dbs)/60*.26*(WIDTH-2), .8*HEIGHT+3,2 + max(max_dbs)/60*.26*(WIDTH-2),  HEIGHT - 4), outline=(255,0,0), fill=(255,0,0))
			st7735.display(img)
			if step_counter % time_interval == 0:
				draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
				display_print(f"CSV...", coords=(.0, .3), font=font)
				st7735.display(img)
				av_weather = np.mean(weather_arr, axis=0)
				assert len(av_weather) == 4
				data_dict["Temp"] = av_weather[0].astype("float16")
				sql_dict["Temp"] = data_dict["Temp"]
				data_dict["Pressure"] = av_weather[1].astype("float16")
				sql_dict["Pres"] = data_dict["Pressure"]
				data_dict["Humidity"] = av_weather[2].astype("float16")
				sql_dict["Hum"] = data_dict["Humidity"]
				data_dict["Light"] = av_weather[3].astype("float16")
				sql_dict["Light"] = data_dict["Light"]
				data_dict["Time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
				with open(f"record-{csv_file_name}.csv", "a+") as f:
					writer = csv.DictWriter(f, fieldnames=header_row)
					writer.writerow(data_dict)
					f.close()
				# draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
				display_print(f"SQL...", coords=(.3, .3), font=font)
				st7735.display(img)
				data_dict = data_dict_init.copy()
				sql_insert(sql_dict)
				# draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
				display_print(f"Done!", coords=(.6, .3), font=font)
				st7735.display(img)
				sql_dict = {}
		sd.wait()
		data = rec_data.copy()
		new_data = True
except KeyboardInterrupt:
    print("Halting")
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
#    display_print(f"Goodbye", coords=(.3, .4), font=font)
    st7735.display(img)
#    time.sleep(2)
#    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
#    st7735.display(img)
    st7735.set_backlight(0)
    sys.exit(0)

