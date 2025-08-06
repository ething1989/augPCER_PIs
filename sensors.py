import time
import threading

# --- BME680 Setup ---
try:
    import board
    import busio
    import adafruit_bme680
except ImportError as e:
    board = busio = adafruit_bme680 = None

# Light and motion sensors use GPIO
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

class SingleReadSensors:
    def __init__(self, light_pin=17, motion_pin=27, counting_interval=60):
        self.samples = []
        self.light_pin = light_pin
        self.motion_pin = motion_pin
        self.counting_interval = counting_interval  # seconds per abundance "snapshot"
        self._stop_event = threading.Event()
        self.motion_count = 0
        self.abundance = 0  # Abundance score for current interval (0 or 1)
        self._last_motion = 0
        self._start_time = time.time()

        # Attempt BME680
        if adafruit_bme680:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.bme680 = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=0x77)
            except Exception as e:
                print(f"BME680 initialization failed: {e}")
                self.bme680 = None
        else:
            print("adafruit_bme680 library not installed.")
            self.bme680 = None

        # GPIO Setup
        if GPIO:
            GPIO.setmode(GPIO.BCM)
            # Digital light (just reads high/low)
            GPIO.setup(self.light_pin, GPIO.IN)
            # Motion sensor (PIR)
            GPIO.setup(self.motion_pin, GPIO.IN)
            # Ensure cleanup at exit
        else:
            print("RPi.GPIO not installed (sensors.py)")

        self.thread = threading.Thread(target=self._motion_counter_thread, daemon=True)
        self.thread.start()

    def _motion_counter_thread(self):
        """Thread: counts unique motion events, max 1 per minute."""
        while not self._stop_event.is_set():
            try:
                # Edge detection: rising (motion detected)
                if GPIO:
                    val = GPIO.input(self.motion_pin)
                    if val and not self._last_motion:
                        # rising edge - a new trigger
                        self.motion_count += 1
                    self._last_motion = val
            except Exception as e:
                pass

            # Each full interval, calculate abundance
            now = time.time()
            if now - self._start_time >= self.counting_interval:
                # Abundance score: record if there was at least 1 activation this interval
                self.abundance = 1 if self.motion_count > 0 else 0
                self.motion_count = 0  # Reset for next interval
                self._start_time = now

            time.sleep(0.1)  # ~10 Hz polling for PIR

    def get(self) -> dict:
        sensors_dict = {}

        # --- BME680 readings ---
        if self.bme680:
            try:
                sensors_dict["temp"] = self.bme680.temperature
                sensors_dict["pressure"] = self.bme680.pressure
                sensors_dict["humidity"] = self.bme680.humidity
                sensors_dict["gas"] = self.bme680.gas
            except Exception as e:
                sensors_dict["temp"] = sensors_dict["pressure"] = None
                sensors_dict["humidity"] = sensors_dict["gas"] = None
                print("BME680 read error:", e)
        else:
            sensors_dict["temp"] = sensors_dict["pressure"] = None
            sensors_dict["humidity"] = sensors_dict["gas"] = None

        # Light sensor (digital)
        if GPIO:
            try:
                sensors_dict["light"] = GPIO.input(self.light_pin)  # 1=light, 0=dark
            except Exception as e:
                sensors_dict["light"] = None
                print("Light sensor error:", e)
        else:
            sensors_dict["light"] = None

        # Motion abundance over last interval
        sensors_dict["abundance"] = self.abundance

        # Store in samples for get_average()
        self.samples.append(sensors_dict.copy())
        # Optional: trim samples list to last N if you want to cap memory use

        return sensors_dict

    def get_average(self) -> dict:
        # Average last interval samples (for e.g. every N minutes)
        keys = ["temp", "pressure", "humidity", "gas", "light", "abundance"]
        avg_data = {k: 0 for k in keys}
        num_samples = len(self.samples)

        if num_samples == 0:
            return avg_data

        for sample in self.samples:
            for k in keys:
                if sample.get(k) is not None:
                    avg_data[k] += sample[k]

        for k in keys:
            avg_data[k] /= num_samples

        # Reset samples if you’re sampling per-interval
        self.samples.clear()
        return avg_data

    def stop(self):
        self._stop_event.set()
        self.thread.join()
        if GPIO:
            GPIO.cleanup()

# Microphone (USB mic) is not handled here; 
# audio recording is typically done separately via arecord/pyaudio, 
# as in your audio scripts.

if __name__ == "__main__":
    # Simple test loop
    sensors = SingleReadSensors()
    try:
        for i in range(5):
            print(sensors.get())
            time.sleep(2)
        print("Averages:", sensors.get_average())
    except KeyboardInterrupt:
        pass
    finally:
        sensors.stop()
