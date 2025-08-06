import sounddevice as sd
import numpy as np
import threading

class Stream:
    def __init__(self, duration=3, sr=48000, channels=1, device=None):
        sd.default.samplerate = sr
        sd.default.channels = channels
        self.sr = sr
        self.channels = channels
        self.buffer_size = sr * duration
        self.buffer = np.zeros((self.buffer_size, channels), dtype='float32')
        self.idx = 0
        self.lock = threading.Lock()
        self.device = device
        self.amplification_factor = 4  # Adjust amplification factor here

    def audio_callback(self, indata, frames, *_):
        with self.lock:
            # Apply amplification
            amplified_data = indata * self.amplification_factor
            
            end = (self.idx + frames) % self.buffer_size
            if self.idx + frames <= self.buffer_size:
                self.buffer[self.idx:self.idx + frames] = amplified_data
            else:
                split = self.buffer_size - self.idx
                self.buffer[self.idx:] = amplified_data[:split]
                self.buffer[:end] = amplified_data[split:]
            self.idx = end

    def normalize(self, data):
        # Maintain normalization option as it was
        return data - np.mean(data, axis=0)

    def get_audio(self):
        with self.lock:
            return self.normalize(np.roll(self.buffer, -self.idx, axis=0).flatten())

    def start(self):
        self.stream = sd.InputStream(
            samplerate=self.sr,
            channels=self.channels,
            callback=self.audio_callback,
            blocksize=4096,
            device=self.device
        )
        self.stream.start()

    def stop(self):
        self.stream.stop()
        self.stream.close()

    def record_nb(self, seconds):
        self.data = sd.rec(self.sr * seconds, device=self.device)

    def record_wait(self):
        sd.wait()
        return self.normalize(self.data.reshape(-1))

# Example usage
if __name__ == "__main__":
    stream = Stream()
    stream.start()
    
    try:
        sd.sleep(3000)  # Placeholder for continuous or session-based audio capture
    except KeyboardInterrupt:
        stream.stop()
