import sounddevice as sd
import numpy as np
import threading

class Stream:
    def __init__(self, duration=3, sr=48000, channels=1, device=None):
        sd.default.samplerate = sr
        sd.default.channels = channels
        self.sr = sr
        self.channels = channels
        self.buffer_size = int(sr * duration)
        self.buffer = np.zeros((self.buffer_size, channels), dtype='float32')
        self.idx = 0
        self.lock = threading.Lock()
        self.device = device
        self.stream = None
        self.data = None  # For blocking record use

    def audio_callback(self, indata, frames, *_):
        with self.lock:
            end = (self.idx + frames) % self.buffer_size
            if self.idx + frames <= self.buffer_size:
                self.buffer[self.idx:self.idx + frames] = indata
            else:
                split = self.buffer_size - self.idx
                self.buffer[self.idx:] = indata[:split]
                self.buffer[:end] = indata[split:]
            self.idx = end

    def normalize(self, data):
        if data.size == 0:
            return data
        return (data - np.mean(data)) / (np.std(data) + 1e-7)

    def get_audio(self):
        with self.lock:
            current_idx = self.idx
            data = np.roll(self.buffer, -current_idx, axis=0).copy()
        return self.normalize(data.flatten())

    def start(self):
        if self.stream is None:
            self.stream = sd.InputStream(
                samplerate=self.sr,
                channels=self.channels,
                callback=self.audio_callback,
                blocksize=4096,
                device=self.device
            )
            self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    # Non-blocking (async) record. Use if you want a single sample using sd.rec().
    def record_nb(self, seconds):
        self.data = sd.rec(
            int(self.sr * seconds),
            samplerate=self.sr,
            channels=self.channels,
            device=self.device
        )

    # Wait for an nb-record to finish, return rescaled audio.
    def record_wait(self):
        sd.wait()
        return self.normalize(self.data.reshape(-1))

if __name__ == "__main__":
    # Example usage: continuous background stream
    print("Starting audio stream for test. Press Ctrl+C to exit.")
    stream = Stream(duration=3)  # Set duration (seconds) for rolling window
    stream.start()
    import time
    try:
        for _ in range(5):
            audio = stream.get_audio()
            print(f"Current buffer shape: {audio.shape}, mean={np.mean(audio):.4f}")
            time.sleep(1)
        # Example: blocking single-shot recording
        print("Performing 2-second blocking recording...")
        stream.record_nb(2)
        result = stream.record_wait()
        print(f"Blocking audio shape: {result.shape}, mean={np.mean(result):.4f}")
    except KeyboardInterrupt:
        print("Exiting test.")
    finally:
        stream.stop()
