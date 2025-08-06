import os
import time
import glob
import subprocess
import board
import busio
from datetime import datetime
import shutil
import sys

# TRY ALL LIBRARIES, FALL BACK GRACEFULLY
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
        rc = subprocess.run(['libcamera-still', '-o', imagefile, '-t', '1000', '--nopreview'],
                            capture_output=True)
        if os.path.exists(imagefile):
            return "Camera: test OK, image saved", imagefile
        else:
            rc = subprocess.run(['fswebcam', imagefile], capture_output=True)
            if os.path.exists(imagefile):
                return "Camera: USB webcam test OK, image saved", imagefile
            return f"Camera: test failed, {rc.stderr.decode()}", None
    except Exception as e:
        return f"Camera: test failed, {e}", None

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
        pms = PMS7003(device='/dev/ttyS0')  # Adjust if needed
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

    # Test camera
    cam_result, cam_img = test_camera()
    outputs.append(cam_result)
    if cam_img:
        shutil.copy(cam_img, usb_mount)

    # RTC and possible clock update
    rtc_output, rtc_obj = test_rtc()
    outputs.append(rtc_output)

    gps_line, gps_time = test_gps()
    outputs.append(gps_line)   # << ONLY APPENDED ONCE, now

    ntp_time = get_internet_time()

    # Only update RTC clock with a valid fix/time
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

    # Test all sensors
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

    # Save results
    outfile = os.path.join(usb_mount, "test_all_sensors_result.txt")
    with open(outfile, "w") as f:
        dt_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"Test run: {dt_string}\n")
        for out in outputs:
            print(out)
            f.write(out + "\n")
    print(f"\nLog written to {outfile}")

    # RUN main.py after test/report is done
    print("Running main.py ...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except Exception as e:
        print(f"Failed to run main.py: {e}")

if __name__ == "__main__":
    main()
