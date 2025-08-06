import numpy as np
import os
import subprocess
import time
import pandas as pd
from collections import defaultdict, OrderedDict
from model import Model
from sound import Stream
from sensors import SingleReadSensors
import bioacoustics
from datetime import datetime

# SET THIS TO YOUR SITE OR INIT FROM test-all-sensors.py
gps_startup_loc = "42.2949,-83.7101"

AUDIO_DEVICE_INDEX = 1
DATA_FOLDER = "data"
MOUNT_POINT = "/mnt/usb"
USB_DEVICE = "/dev/sda1"
CYCLE_MINUTES = 10
CYCLES_PER_WRITE = 1
CYCLES_PER_SHUTDOWN = 6
FILENAME_FMT = "%Y-%m-%d.csv"

def calculate_iaq(gas, humidity, temperature):
    try:
        if gas is None or gas <= 0 or humidity is None or temperature is None:
            return None
        optimal_hum = 40.0
        humidity_weight = 0.25
        humidity_score = max(0, min(100, 100 * abs(humidity - optimal_hum) / (100 - optimal_hum)))
        gas_reference = 250000.0
        gas_weight = 0.75
        gas_score = max(0, min(100, 100 * min(gas, gas_reference) / gas_reference))
        temperature_weight = 0.15
        temp_score = max(0, min(100, 100 * abs(temperature - 22) / 40))
        iaq = (humidity_weight * humidity_score) + (gas_weight * (100 - gas_score)) + (temperature_weight * (100 - temp_score))
        iaq_index = round((1 - iaq / 100) * 500, 2)
        iaq_index = max(0, min(500, iaq_index))
        return iaq_index
    except Exception:
        return None

def ensure_usb_mounted(mount_point=MOUNT_POINT, device=USB_DEVICE):
    if not os.path.ismount(mount_point):
        os.makedirs(mount_point, exist_ok=True)
        subprocess.run(["sudo", "mount", device, mount_point, "-o", "uid=1000,gid=1000"], check=True)

def safe_local_append(df, filename, header):
    try:
        os.makedirs(DATA_FOLDER, exist_ok=True)
        local_file_path = f"{DATA_FOLDER}/{filename}"
        file_exists = os.path.exists(local_file_path)
        df.to_csv(local_file_path, mode='a', header=header and not file_exists, index=False)
        print(f"Appended locally to {local_file_path}")
    except Exception as e:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fallback_filename = f"{DATA_FOLDER}/{filename.split('.')[0]}_{timestamp}.csv"
        df.to_csv(fallback_filename, index=False)
        print(f"Write error for {filename}: {e}. Data saved to {fallback_filename} instead.")

def safe_usb_append(df, filename, header):
    try:
        ensure_usb_mounted()
        usb_file_path = f"{MOUNT_POINT}/{filename}"
        file_exists = os.path.exists(usb_file_path)
        df.to_csv(usb_file_path, mode='a', header=header and not file_exists, index=False)
        print(f"Appended {len(df)} row(s) to USB: {usb_file_path}")
    except Exception as e:
        print(f"USB append error: {e}. Will retry next cycle.")

def print_status_bar(minute_idx, cycle_idx, total_minutes, total_cycles):
    print(f"[{datetime.now()}] Cycle {cycle_idx+1}/{total_cycles}, Minute {minute_idx+1}/{total_minutes}", end='\r', flush=True)

def process_sensor_data(sensors, sensor_sums, sensor_counts, errors, motion_trips):
    try:
        sensor_data = sensors.get()
        for key, value in sensor_data.items():
            if value is not None:
                if key == "motion_tripped":
                    if value:
                        motion_trips[0] += 1
                elif key in {"temp", "humidity", "pressure", "gas", "light"}:
                    sensor_sums[key] += value
                    sensor_counts[key] += 1
    except Exception as e:
        errors.append(f"Sensor reading error: {e}")

def analyze_audio_data(audio_chunks, stream_sr, errors):
    bioacoustic_indices = {"ADI": 0, "ACI": 0, "AEI": 0, "BI": 0, "NDSI": 0}
    if audio_chunks:
        try:
            full_audio_data = np.concatenate(audio_chunks)
            bioacoustic_indices = bioacoustics.bioacoustic_analysis(full_audio_data, stream_sr)
        except Exception as e:
            errors.append(f"Bioacoustic analysis error: {e}")
    return bioacoustic_indices

def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    model = Model("model_int8")
    stream = Stream(device=AUDIO_DEVICE_INDEX)
    sensors = SingleReadSensors()
    stream.start()
    try:
        known_birds = set()
        filename = datetime.now().strftime(FILENAME_FMT)
        static_header = [
            "timestamp", "gps",
            "Temperature (C)", "Temperature (F)",
            "Pressure (hPa)", "Pressure (inHg)", "Humidity (%)",
            "Gas", "IAQ", "Light", "Motion Trips",
            "ADI", "ACI", "AEI", "BI", "NDSI",
            "Total Species", "Total Detections", "Temp Running Avg (C)"
        ]
        cycles_since_write = 0
        batch_rows = []
        model_window_size = 144000  # CHANGE as needed for your model

        for cycle_idx in range(CYCLES_PER_SHUTDOWN):
            print(f"\n=== Begin Cycle {cycle_idx+1}/{CYCLES_PER_SHUTDOWN} at {datetime.now()} ===")
            # Running tallies
            species_counts = defaultdict(int)
            motion_trips = [0]
            errors = []
            temperatures = []
            accum_sensor_sums = defaultdict(float)
            accum_sensor_counts = defaultdict(int)
            bio_chunks = []
            running_audio_buffer = np.array([], dtype='float32')
            minute_seconds = int(CYCLE_MINUTES * 60)
            cycle_start = time.time()
            while time.time() - cycle_start < minute_seconds:
                audio_chunk = stream.get_audio()
                if audio_chunk is not None and np.any(audio_chunk):
                    running_audio_buffer = np.concatenate([running_audio_buffer, audio_chunk])
                    bio_chunks.append(audio_chunk)
                    # Process all full windows in buffer (non-overlapping)
                    while len(running_audio_buffer) >= model_window_size:
                        model_window = running_audio_buffer[:model_window_size]
                        running_audio_buffer = running_audio_buffer[model_window_size:]
                        try:
                            labels = model.predict_threshold([model_window], min_p=0.10)
                            for label, prob in labels:
                                species_counts[label] += 1
                                known_birds.add(label)
                        except Exception as e:
                            errors.append(f"Audio processing error: {e}")
                process_sensor_data(sensors, accum_sensor_sums, accum_sensor_counts, errors, motion_trips)
                if "temp" in accum_sensor_sums and accum_sensor_counts["temp"] > 0:
                    temperatures.append(accum_sensor_sums["temp"] / accum_sensor_counts["temp"])
                time.sleep(1)

            # After cycle: sensor summaries
            temp_c = accum_sensor_sums["temp"] / accum_sensor_counts["temp"] if accum_sensor_counts["temp"] > 0 else None
            temp_f = round(temp_c * 9 / 5 + 32, 2) if temp_c is not None else None
            temperature_running_avg = round(np.mean(temperatures), 2) if temperatures else None
            pressure = accum_sensor_sums["pressure"] / accum_sensor_counts["pressure"] if accum_sensor_counts["pressure"] > 0 else None
            pressure_inhg = round(pressure * 0.02953, 2) if pressure is not None else None
            humidity = accum_sensor_sums["humidity"] / accum_sensor_counts["humidity"] if accum_sensor_counts["humidity"] > 0 else None
            gas = accum_sensor_sums["gas"] / accum_sensor_counts["gas"] if accum_sensor_counts["gas"] > 0 else None
            iaq = calculate_iaq(gas, humidity, temperature_running_avg)
            light = int((accum_sensor_sums["light"] / accum_sensor_counts["light"]) > 0) if accum_sensor_counts["light"] > 0 else 0
            gps = gps_startup_loc
            bioacoustic_indices = analyze_audio_data(bio_chunks, stream.sr, errors)

            # Dynamically build full header with all ever-seen birds
            all_birds = sorted(known_birds)
            header = static_header + all_birds

            # Build consistent row
            row = OrderedDict()
            row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row["gps"] = gps
            row["Temperature (C)"] = round(temp_c,2) if temp_c is not None else None
            row["Temperature (F)"] = temp_f
            row["Pressure (hPa)"] = round(pressure,2) if pressure is not None else None
            row["Pressure (inHg)"] = pressure_inhg
            row["Humidity (%)"] = round(humidity,2) if humidity is not None else None
            row["Gas"] = round(gas,2) if gas is not None else None
            row["IAQ"] = iaq
            row["Light"] = light
            row["Motion Trips"] = motion_trips[0]
            row["ADI"] = round(bioacoustic_indices.get("ADI",0),2)
            row["ACI"] = round(bioacoustic_indices.get("ACI",0),2)
            row["AEI"] = round(bioacoustic_indices.get("AEI",0),2)
            row["BI"] = round(bioacoustic_indices.get("BI",0),2)
            row["NDSI"] = round(bioacoustic_indices.get("NDSI",0),2)
            row["Total Species"] = len([k for k,v in species_counts.items() if v > 0])
            row["Total Detections"] = sum(species_counts.values())
            row["Temp Running Avg (C)"] = temperature_running_avg
            for bird in all_birds:
                row[bird] = species_counts.get(bird, 0)

            print("\nCycle summary:", row)
            batch_rows.append(row)
            cycles_since_write += 1

            # Write batch with consistent columns
            if cycles_since_write >= CYCLES_PER_WRITE or (cycle_idx+1) == CYCLES_PER_SHUTDOWN:
                # Fill missing bird columns for all batch rows
                for r in batch_rows:
                    for bird in all_birds:
                        if bird not in r: r[bird] = 0
                df = pd.DataFrame(batch_rows, columns=header)
                safe_local_append(df, filename, header=True)
                safe_usb_append(df, filename, header=True)
                batch_rows = []
                cycles_since_write = 0

        print(f"\nCompleted {CYCLES_PER_SHUTDOWN} cycles. Shutting down Pi.")
        subprocess.run(["sudo", "shutdown", "-h", "now"])

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as exc:
        print(f"\nERROR in main loop: {exc}")
    finally:
        stream.stop()
        print("Audio stream stopped.")

if __name__ == "__main__":
    main()
