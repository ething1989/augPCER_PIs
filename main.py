import numpy as np
import os
import subprocess
import time
import concurrent.futures
import pandas as pd
from collections import defaultdict
from model import Model
from sound import Stream
from sensors import SingleReadSensors
import bioacoustics
from datetime import datetime

# ------------ Hardware Configs (Edit for your setup) ----------------
AUDIO_DEVICE_INDEX = 1             # set to USB mic index for Stream
SENSOR_DEVICE = "bme680"           # Just for your logic–ignored if sensors code auto-detects
DATA_FOLDER = "data"
MOUNT_POINT = "/mnt/usb"
USB_DEVICE = "/dev/sda1"
CYCLE_MINUTES = 9.5                # Data collection per period
SAVE_AFTER_CYCLES = 12             # #periods before saving batch to USB
# ---------------------------------------------------------------------

def ensure_usb_mounted(mount_point=MOUNT_POINT, device=USB_DEVICE):
    if not os.path.ismount(mount_point):
        os.makedirs(mount_point, exist_ok=True)
        subprocess.run(["sudo", "mount", device, mount_point, "-o", "uid=1000,gid=1000"], check=True)

def safe_usb_copy(local_filename, usb_filename):
    try:
        ensure_usb_mounted()
        local_file_path = f"{DATA_FOLDER}/{local_filename}"
        usb_file_path = f"{MOUNT_POINT}/{usb_filename}"
        subprocess.run(["cp", local_file_path, usb_file_path], check=True)
        print(f"Data copied to USB as {usb_file_path}.")
    except Exception as e:
        print(f"USB copy error: {e}. Will retry next cycle.")

def safe_local_write(df, filename, header):
    """Append to CSV in data folder, create if first write."""
    try:
        local_file_path = f"{DATA_FOLDER}/{filename}"
        file_exists = os.path.exists(local_file_path)
        df.to_csv(local_file_path, mode='a', header=header or not file_exists, index=False)
        if not file_exists:
            print(f"Data saved locally as {local_file_path}.")
        else:
            print(f"Data appended locally as {local_file_path}.")
    except Exception as e:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fallback_filename = f"{DATA_FOLDER}/{filename.split('.')[0]}_{timestamp}.csv"
        df.to_csv(fallback_filename, index=False)
        print(f"Write error for {filename}: {e}. Data saved to {fallback_filename} instead.")

def print_status_bar(start_time, total_time, cycle=None, save_cycle=None):
    elapsed_time = time.time() - start_time
    remaining_time = total_time - elapsed_time
    remaining_time = max(remaining_time, 0)
    progress_percentage = (elapsed_time / total_time) * 100
    minutes_progressed = int(elapsed_time // 60)

    status_message = f"[{elapsed_time:.0f}s/{total_time}s] Progress: {progress_percentage:.1f}%, "
    status_message += f"Remaining: {remaining_time:.0f}s, Minutes: {minutes_progressed}"

    if cycle is not None and save_cycle is not None:
        status_message += f" | Current Cycle: {cycle}/{save_cycle}"
        if cycle == save_cycle:
            status_message += " [Saving to USB next cycle]"

    print(status_message, end="\r", flush=True)

def process_audio_chunk(model, audio_data, bird_counts, known_birds, errors):
    try:
        audio_data = np.asarray(audio_data).copy()
        labels = model.predict_threshold([audio_data], min_p=0.15)
        for label, prob in labels:
            bird_counts[label] += 1
            known_birds.add(label)
    except Exception as e:
        errors.append(f"Audio processing error: {e}")

def process_sensor_data(sensors, sensor_sums, sensor_counts, errors, motion_trips):
    try:
        sensor_data = sensors.get()
        for key, value in sensor_data.items():
            if value is not None:
                if key == "motion_tripped":
                    if value:
                        motion_trips[0] += 1   # motion_trips is [int]
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
        errors = []
        start_time = time.time()
        cycle_count = 0
        filename = time.strftime("%Y-%m-%d") + ".csv"  # Overwrite per-day
        header = [
            "timestamp", "Temperature (C)", "Temperature (F)",
            "Pressure (hPa)", "Pressure (inHg)", "Humidity (%)",
            "Gas", "Light", "Motion Trips",
            "ADI", "ACI", "AEI", "BI", "NDSI",
            "Total Species", "Total Detections"
        ]  # Add bird labels dynamically!

        batch_rows = []
        last_save = time.time()

        while True:
            # ============ Start data accumulation for one period =============
            period_audio_chunks = []
            bird_counts  = defaultdict(int)
            sensor_sums  = defaultdict(float)
            sensor_counts = defaultdict(int)
            errors = []
            motion_trips = [0]
            one_period_start = time.time()

            print(f"\n== Period {cycle_count+1} starting: {datetime.now()} ==")
            while time.time() - one_period_start < CYCLE_MINUTES * 60:
                # Print minute status
                elapsed_mins = int((time.time() - one_period_start) // 60)
                if int(time.time() - one_period_start) % 60 == 0:
                    print_status_bar(one_period_start, CYCLE_MINUTES*60, cycle_count+1, SAVE_AFTER_CYCLES)
                # Audio & Model
                audio_data = stream.get_audio()
                if audio_data is not None and np.any(audio_data):
                    process_audio_chunk(model, audio_data, bird_counts, known_birds, errors)
                    period_audio_chunks.append(audio_data)
                # Sensor reads
                process_sensor_data(sensors, sensor_sums, sensor_counts, errors, motion_trips)
                time.sleep(1)

            # ==== After period: summarize and build row ====
            sens_avg = {k: (sensor_sums[k] / sensor_counts[k] if sensor_counts[k]>0 else None) for k in sensor_sums}
            temp_c = sens_avg.get("temp", None)
            temp_f = round(temp_c * 9 / 5 + 32, 2) if temp_c is not None else None
            pressure = sens_avg.get("pressure", None)
            pressure_inhg = round(pressure * 0.02953, 2) if pressure is not None else None
            humidity = sens_avg.get("humidity", None)
            gas = sens_avg.get("gas", None)
            light = int(sens_avg.get("light", 0) > 0) if "light" in sens_avg else 0

            bioacoustic_indices = analyze_audio_data(period_audio_chunks, stream.sr, errors)
            # Bird results
            row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Temperature (C)": round(temp_c,2) if temp_c is not None else None,
                "Temperature (F)": temp_f,
                "Pressure (hPa)": round(pressure,2) if pressure is not None else None,
                "Pressure (inHg)": pressure_inhg,
                "Humidity (%)": round(humidity,2) if humidity is not None else None,
                "Gas": round(gas,2) if gas is not None else None,
                "Light": light,
                "Motion Trips": motion_trips[0],
                "ADI": round(bioacoustic_indices.get("ADI",0),2),
                "ACI": round(bioacoustic_indices.get("ACI",0),2),
                "AEI": round(bioacoustic_indices.get("AEI",0),2),
                "BI": round(bioacoustic_indices.get("BI",0),2),
                "NDSI": round(bioacoustic_indices.get("NDSI",0),2),
                "Total Species": sum(1 for v in bird_counts.values() if v>0),
                "Total Detections": sum(bird_counts.values()),
            }
            # Add birds in consistent order
            for bird in sorted(known_birds):
                row[bird] = bird_counts[bird]
                if bird not in header: header.append(bird)

            # Save this row in batch
            batch_rows.append(row)
            print("Period summary:", row)

            # ========== after SAVE_AFTER_CYCLES, append DataFrame and save ========
            if len(batch_rows) >= SAVE_AFTER_CYCLES:
                df = pd.DataFrame(batch_rows, columns=header)
                safe_local_write(df, filename, header=True)
                safe_usb_copy(filename, filename)
                batch_rows.clear()

            # Write one row as an extra local save for robustness
            elif len(batch_rows) == 1:
                df = pd.DataFrame([row], columns=header)
                safe_local_write(df, filename, header=True)
                # No USB write yet

            # (Optional) reboot and copy on 24hr cycle
            if time.time() - start_time > 24 * 60 * 60:
                if batch_rows:
                    df = pd.DataFrame(batch_rows, columns=header)
                    safe_local_write(df, filename, header=True)
                    safe_usb_copy(filename, filename)
                print("Rebooting system after 24hr.")
                subprocess.run(["sudo", "reboot"])

            cycle_count += 1

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        stream.stop()
        print("Audio stream stopped.")

if __name__ == "__main__":
    main()
