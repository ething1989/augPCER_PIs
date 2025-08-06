import os
import time
import glob
import subprocess
import board
import busio
from datetime import datetime
import shutil
import sys
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box

def load_labels_mapping(labels_file_path):
    sci_to_eng = {}
    with open(labels_file_path, "r") as lf:
        for line in lf:
            if "_" in line:
                sci, eng = line.strip().split("_", 1)
                sci_to_eng[sci.strip().lower()] = eng.strip()
    return sci_to_eng

def get_overlapping_tiles(gps_lat, gps_lon, tile_folder, buffer_km=50):
    DEG = 30
    buffer_deg_lat = buffer_km / 110.574
    buffer_deg_lon = buffer_km / (111.320 * abs(np.cos(np.radians(gps_lat))) + 0.0001) # avoid zero at poles
    min_lat = gps_lat - buffer_deg_lat
    max_lat = gps_lat + buffer_deg_lat
    min_lon = gps_lon - buffer_deg_lon
    max_lon = gps_lon + buffer_deg_lon
    lat_bins = list(range(-90, 90, DEG))
    lon_bins = list(range(-180, 180, DEG))
    tile_lat = set()
    tile_lon = set()
    for lat in lat_bins:
        if lat <= max_lat and (lat + DEG) >= min_lat:
            tile_lat.add(lat)
    for lon in lon_bins:
        if lon <= max_lon and (lon + DEG) >= min_lon:
            tile_lon.add(lon)
    tiles = []
    for lat in tile_lat:
        for lon in tile_lon:
            fname = f'birds_tile_{lat}_{lon}.gpkg'
            fpath = os.path.join(tile_folder, fname)
            if os.path.exists(fpath):
                tiles.append(fpath)
    return tiles

def fast_species_list_multi_files(gpkg_files, gps_lat, gps_lon, buffer_km=50):
    found_species = set()
    point = Point(gps_lon, gps_lat)
    for file in gpkg_files:
        gdf = gpd.read_file(file)
        if len(gdf) == 0:
            continue
        gdf = gdf.to_crs(epsg=3395)
        pt_metric = gpd.GeoSeries([point], crs=4326).to_crs(epsg=3395).iloc[0]
        zone = pt_metric.buffer(buffer_km * 1000)
        bbox = zone.bounds
        if not hasattr(gdf, "sindex"):
            gdf.sindex
        poss = list(gdf.sindex.intersection(bbox))
        gdfcut = gdf.iloc[poss]
        found = gdfcut[gdfcut.geometry.intersects(zone)]
        for s in found["sci_name"].unique():
            found_species.add(str(s).strip().lower())
    return list(found_species)

def update_bird_list_from_gps(
    tile_folder, labels_file_path, model_py_path, gps_lat, gps_lon, buffer_km=50
):
    print(f"[BirdList] Looking for relevant 30x30 GPKGs near: {gps_lat}, {gps_lon} (buffer {buffer_km}km)")
    sci_to_eng = load_labels_mapping(labels_file_path)
    gpkg_files = get_overlapping_tiles(gps_lat, gps_lon, tile_folder, buffer_km)
    if not gpkg_files:
        print("[BirdList] No GPKG tiles found. Falling back to all birds.")
        found_english = sorted(set(sci_to_eng.values()))
    else:
        sci_names_found = fast_species_list_multi_files(gpkg_files, gps_lat, gps_lon, buffer_km)
        found_english = [sci_to_eng[sci] for sci in sci_names_found if sci in sci_to_eng]
        found_english = sorted(set(found_english))
        if not found_english:
            print("[BirdList] No birds found in buffer region; using all birds in labels.txt.")
            found_english = sorted(set(sci_to_eng.values()))
    with open(model_py_path, encoding='utf8') as f:
        lines = f.readlines()
    new_lines = []
    inside_bird_list = False
    for line in lines:
        if line.strip().startswith('pantanal_birds'):
            inside_bird_list = True
            new_lines.append('pantanal_birds = {\n')
            for b in found_english:
                new_lines.append(f'    "{b}",\n')
            new_lines.append('}\n')
        elif inside_bird_list:
            if line.strip() == "}":
                inside_bird_list = False
        else:
            new_lines.append(line)
    with open(model_py_path, 'w', encoding='utf8') as f:
        f.writelines(new_lines)
    print(f"[BirdList] pantanal_birds set updated in {model_py_path} with {len(found_english)} species.")

def update_bird_list_all(labels_file_path, model_py_path):
    sci_to_eng = load_labels_mapping(labels_file_path)
    english_names = sorted(set(sci_to_eng.values()))
    with open(model_py_path, encoding='utf8') as f:
        lines = f.readlines()
    new_lines = []
    inside_bird_list = False
    for line in lines:
        if line.strip().startswith('pantanal_birds'):
            inside_bird_list = True
            new_lines.append('pantanal_birds = {\n')
            for b in english_names:
                new_lines.append(f'    "{b}",\n')
            new_lines.append('}\n')
        elif inside_bird_list:
            if line.strip() == "}":
                inside_bird_list = False
        else:
            new_lines.append(line)
    with open(model_py_path, 'w', encoding='utf8') as f:
        f.writelines(new_lines)
    print(f"[BirdList] No GPS, so all birds in model.py.")

def ensure_gpsd(required=True):
    gps_dev_candidates = ['/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial0']
    try:
        subprocess.run(['sudo', 'killall', 'gpsd'], check=False)
        time.sleep(1)
        for dev in gps_dev_candidates:
            if os.path.exists(dev):
                subprocess.Popen(['sudo', 'gpsd', dev, '-F', '/var/run/gpsd.sock'])
                print(f"[GPSD] Started gpsd on {dev}")
                time.sleep(2)
                return dev
        if required:
            print("[GPSD] No GPS device found! Will continue, but gps tests will fail.")
    except Exception as e:
        print(f"[GPSD] Error setting up gpsd: {e}")
    return None

# TRY/EXCEPT sensor imports
try:
    import adafruit_bme680
except Exception:
    adafruit_bme680 = None
try:
    import adafruit_ds3231
except Exception:
    adafruit_ds3231 = None
try:
    import adafruit_scd4x
except Exception:
    adafruit_scd4x = None
try:
    from pms7003 import PMS7003
except Exception:
    PMS7003 = None
try:
    from adafruit_mcp3xxx.mcp3008 import MCP3008
    from adafruit_mcp3xxx.analog_in import AnalogIn
except Exception:
    MCP3008 = None
    AnalogIn = None
try:
    import spidev
except Exception:
    spidev = None

def find_usb_mount():
    for mnt in glob.glob('/media/*/*'):
        if os.path.isdir(mnt) and os.access(mnt, os.W_OK):
            return mnt
    return "/tmp"

def test_camera(imagefile="test_cam.jpg"):
    try:
        rc = subprocess.run(['libcamera-still', '-o', imagefile, '-t', '1000', '--nopreview'], capture_output=True)
        if os.path.exists(imagefile):
            return "Camera: test OK, image saved", imagefile
        else:
            rc = subprocess.run(['fswebcam', imagefile], capture_output=True)
            if os.path.exists(imagefile):
                return "Camera: USB webcam test OK, image saved", imagefile
            return f"Camera: test failed, {rc.stderr.decode()}", None
    except Exception as e:
        return f"Camera: test failed: {e}", None

def test_bme680():
    if adafruit_bme680 is None:
        return "BME680: test failed: adafruit_bme680 lib missing"
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x77)
        out = {
            "temp": sensor.temperature,
            "humidity": sensor.humidity,
            "pressure": sensor.pressure,
            "gas": sensor.gas
        }
        return f"BME680: {out}"
    except Exception as e:
        return f"BME680: test failed: {e}"

def test_scd40():
    if adafruit_scd4x is None:
        return "SCD40: test failed: adafruit_circuitpython_scd4x missing"
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        scd = adafruit_scd4x.SCD4X(i2c)
        scd.start_periodic_measurement()
        time.sleep(5)
        if scd.data_ready:
            co2 = scd.CO2
            temp = scd.temperature
            hum = scd.relative_humidity
            return f"SCD40: CO2={co2}ppm, temp={temp:.2f}C, humidity={hum:.2f}%"
        return "SCD40: no data ready: try longer delay"
    except Exception as e:
        return f"SCD40: test failed: {e}"

def test_pms7003():
    if PMS7003 is None:
        return "PMS7003: test failed: pms7003 lib missing"
    try:
        pms = PMS7003(device='/dev/ttyS0')
        data = pms.read()
        return 'PMS7003: ' + ', '.join([f'{k}={v}' for k, v in data.items()])
    except Exception as e:
        return f"PMS7003: test failed: {e}"

def test_rtc():
    if adafruit_ds3231 is None:
        return "RTC: test failed: adafruit_ds3231 lib missing", None
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        rtc = adafruit_ds3231.DS3231(i2c)
        dt = rtc.datetime
        return f"RTC: {dt}", rtc
    except Exception as e:
        return f"RTC: test failed: {e}", None

def update_rtc(rtc, dt):
    try:
        rtc.datetime = dt
        return f"RTC updated to: {dt}"
    except Exception as e:
        return f"RTC update failed: {e}"

def test_light_digital(pin=17):
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN)
        value = GPIO.input(pin)
        GPIO.cleanup()
        return f"Light (digital): {'light' if value else 'dark'} (val={value})"
    except Exception as e:
        return f"Light (digital): not found/test failed: {e}"

def test_motion(gpio_pin=27):
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_pin, GPIO.IN)
        value = GPIO.input(gpio_pin)
        GPIO.cleanup()
        return f"Motion: detected={value}"
    except Exception as e:
        return f"Motion: not found/test failed: {e}"

def test_mcp3008_channel(channel, label):
    if MCP3008 is None or AnalogIn is None or spidev is None:
        return f"{label}: test failed: MCP3008 lib/methods missing"
    try:
        import digitalio
        spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
        cs = digitalio.DigitalInOut(board.D5)
        mcp = MCP3008(spi, cs)
        chan = AnalogIn(mcp, channel)
        return f"{label}: ADC={chan.value}, voltage={chan.voltage:.2f}V"
    except Exception as e:
        return f"{label}: test failed: {e}"

def test_soil_moisture():
    return test_mcp3008_channel(2, "Soil moisture")

def test_water_level():
    return test_mcp3008_channel(3, "Water level")

def test_wind():
    return test_mcp3008_channel(4, "Wind (speed/direction)")

def test_mq135():
    return test_mcp3008_channel(1, "MQ135 (gas sensor)")

def test_light_analog():
    return test_mcp3008_channel(0, "Light (analog)")

def test_mic(wavfile='testmic.wav'):
    try:
        rc = subprocess.run(['arecord', '-D', 'plughw:1,0', '-d', '2', '-f', 'cd', wavfile], capture_output=True)
        if os.path.exists(wavfile):
            return "Microphone: test OK"
        else:
            return "Microphone: test failed (arecord did not create file)"
    except Exception as e:
        return f"Microphone: test failed: {e}"

def test_pico(serial_path=None):
    try:
        import serial
    except ImportError:
        return "Pico: pyserial not installed"
    try:
        serials = glob.glob('/dev/ttyACM*')
        serial_path = serial_path or (serials[0] if serials else None)
        if not serial_path:
            return "Pico: /dev/ttyACM* not found"
        with serial.Serial(serial_path, 115200, timeout=5) as ser:
            ser.write(b"SNAP\n")
            ser.flush()
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                return "Pico: no response"
            return f"Pico: {line[:120]}"
    except Exception as e:
        return f"Pico: test failed: {e}"

def test_gps(timeout=10):
    try:
        import gpsd
    except ImportError:
        return "GPS: gpsd-py3 not installed", None
    try:
        gpsd.connect()
        start = time.time()
        while time.time() - start < timeout:
            pkt = gpsd.get_current()
            if pkt.mode > 1:
                lat, lon = pkt.position()
                time_utc = pkt.time
                msg = f"GPS: FIXED, lat={lat:.6f}, lon={lon:.6f}, UTC={time_utc}"
                print(msg)
                return msg, time_utc
            time.sleep(1)
        return "GPS: no GPS fix in timeout", None
    except Exception as e:
        return f"GPS: not found or test failed: {e}", None

def get_internet_time():
    try:
        return datetime.utcnow()
    except Exception:
        return None

def main():
    outputs = []
    usb_mount = find_usb_mount()
    dev = ensure_gpsd()
    cam_result, cam_img = test_camera()
    outputs.append(cam_result)
    if cam_img:
        shutil.copy(cam_img, usb_mount)
    rtc_output, rtc_obj = test_rtc()
    outputs.append(rtc_output)
    gps_line, gps_time = test_gps()
    outputs.append(gps_line)
    ntp_time = get_internet_time()
    if gps_time and rtc_obj:
        try:
            newdt = datetime.strptime(gps_time.split('.')[0], "%Y-%m-%dT%H:%M:%S")
            rtc_set = update_rtc(rtc_obj, newdt.timetuple())
            outputs.append(f"RTC set from GPS: {rtc_set}")
        except Exception as e:
            outputs.append(f"RTC set from GPS failed: {e}")
    elif isinstance(ntp_time, datetime) and rtc_obj:
        rtc_set = update_rtc(rtc_obj, ntp_time.timetuple())
        outputs.append(f"RTC set from NTP: {rtc_set}")
    outputs.append(test_bme680())
    outputs.append(test_scd40())
    outputs.append(test_pms7003())
    outputs.append(test_light_digital())
    outputs.append(test_light_analog())
    outputs.append(test_mq135())
    outputs.append(test_soil_moisture())
    outputs.append(test_water_level())
    outputs.append(test_wind())
    outputs.append(test_motion())
    outputs.append(test_mic())
    outputs.append(test_pico())
    outfile = os.path.join(usb_mount, "test_all_sensors_result.txt")
    with open(outfile, "w") as f:
        dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"Test run: {dt_string}\n")
        for out in outputs:
            print(out)
            f.write(out + "\n")
    print(f"\nLog written to {outfile}")
    gps_lat, gps_lon = None, None
    if gps_line and 'lat=' in gps_line and 'lon=' in gps_line:
        try:
            parts = gps_line.split(',')
            lat = [p for p in parts if 'lat=' in p][0].split('=')[1]
            lon = [p for p in parts if 'lon=' in p][0].split('=')[1]
            gps_lat, gps_lon = float(lat), float(lon)
        except Exception as e:
            print(f"[GPS] Could not parse GPS lat/lon: {e}")
    if gps_lat and gps_lon:
        gps_startup_loc = f"{gps_lat},{gps_lon}"
        with open("/tmp/gps_startup_loc.txt", "w") as f:
            f.write(gps_startup_loc)
        print(f"[init] Startup GPS location: {gps_startup_loc}")
    else:
        gps_startup_loc = None
        print("[init] No valid GPS startup location, will fall back to all birds.")
    try:
        tile_folder = os.path.join(usb_mount)
        labels_path = os.path.join(os.path.dirname(__file__), "labels.txt")
        model_py_path = os.path.join(os.path.dirname(__file__), "model.py")
        if os.path.exists(tile_folder) and os.path.exists(labels_path) and os.path.exists(model_py_path):
            if gps_lat and gps_lon:
                update_bird_list_from_gps(
                    tile_folder=tile_folder,
                    labels_file_path=labels_path,
                    model_py_path=model_py_path,
                    gps_lat=gps_lat,
                    gps_lon=gps_lon,
                    buffer_km=50
                )
            else:
                update_bird_list_all(labels_file_path=labels_path, model_py_path=model_py_path)
        else:
            print("[ERROR] Missing tile directory, model.py, or labels.txt for bird range update.")
    except Exception as e:
        print(f"[BirdList] ERROR: {e}")
    print("Starting main.py ...")
    os.execv(sys.executable, ['python3', '/home/juara/juara-field-sensors/main.py'])

if __name__ == "__main__":
    main()
