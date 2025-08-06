import numpy as np
import time
from model import Model
from sound import Stream
from sensors import SingleReadSensors
import bioacoustics
import sounddevice as sd

def pick_usb_device():
    """
    Tries to auto-pick the first USB mic found.
    Returns its index or name if found, else None.
    """
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if "usb" in dev['name'].lower() and dev['max_input_channels'] > 0:
            print(f"Auto-selected USB mic at index {idx}: {dev['name']}")
            return idx
    print("WARNING: Could not auto-detect USB mic; using system default input.")
    return None

def main():
    # List devices for diagnostics
    print("Available Sound Devices:")
    for idx, dev in enumerate(sd.query_devices()):
        io = []
        if dev['max_input_channels'] > 0: io.append("Input")
        if dev['max_output_channels'] > 0: io.append("Output")
        print(f"{idx}: {dev['name']} - {', '.join(io)}")
    
    # Pick USB mic device (override this if you know the right index!)
    device = pick_usb_device()
    stream = Stream(device=device)
    sensors = SingleReadSensors()
    model = Model("model_int8")
    RUN_SECONDS = 60

    stream.start()
    print("Beginning streaming test. Will run for %d seconds." % RUN_SECONDS)

    # Sensors test at startup
    try:
        print("[SENSORS] Startup read:", sensors.get())
    except Exception as e:
        print("[SENSORS ERROR at startup]", e)

    start_time = time.time()
    try:
        all_audio = []
        per_bird_counts = {}
        per_bioacoustics = []
        while time.time() - start_time < RUN_SECONDS:
            t0 = time.time()
            audio = stream.get_audio()
            if audio is None or np.all(audio==0):
                print("(No new audio chunk)")
            else:
                print("[AUDIO] New audio chunk shape:", audio.shape)
                # Run detection anyway
                preds = model.predict_threshold([audio], min_p=0.15)
                if preds:
                    print("[MODEL] Detected:", preds)
                    for label, _ in preds:
                        per_bird_counts[label] = per_bird_counts.get(label, 0) + 1
                all_audio.append(audio)

            # Sensor readings every 10 seconds
            if int(time.time() - start_time) % 10 == 0:
                try:
                    sens = sensors.get()
                    print("[SENSORS]", sens)
                except Exception as e:
                    print("[SENSORS ERROR]", e)

            # Stream a quick bioacoustic calc every 20s
            if int(time.time() - start_time) % 20 == 0 and all_audio:
                try:
                    audio_concat = np.concatenate(all_audio)
                    bi = bioacoustics.bioacoustic_analysis(audio_concat, stream.sr)
                    print("[BIOACOUSTICS]", bi)
                    per_bioacoustics.append(bi)
                except Exception as e:
                    print("[BIOACOUSTICS ERROR]", e)
                all_audio = []

            time.sleep(1)

        print("====== TEST FINISHED ======")
        print("Total bird/class detections:", per_bird_counts)
        if per_bioacoustics:
            print("Bioacoustics, last/avg/all:", per_bioacoustics[-1], "\n", {k: np.mean([b[k] for b in per_bioacoustics if k in b and not isinstance(b[k], str)]) for k in per_bioacoustics[-1]})
        else:
            print("No bioacoustics completed.")
        print("====== END OF SESSION ======")
    finally:
        stream.stop()
        print("Audio stream stopped.")

if __name__ == "__main__":
    main()
