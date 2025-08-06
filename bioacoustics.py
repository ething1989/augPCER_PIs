import numpy as np
import librosa

def compute_adi(y, sr, bands=10, band_width=100):
    # Calculate the Spectrogram
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=1024))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Divide the spectrum into bands and calculate ADI
    freq_bins = np.linspace(0, sr // 2, S.shape[0])
    adi_value = 0
    for i in range(bands):
        band_energy = S_db[(freq_bins >= i * band_width) & (freq_bins < (i + 1) * band_width)]
        if band_energy.size:
            adi_value += np.ptp(band_energy)  # Peak-to-Peak range as diversity measure
    return adi_value

def compute_aci(y, sr):
    # Calculate the acoustic complexity
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=1024))
    aci_value = np.sum(np.var(S, axis=1))  # Sum of variances can represent complexity
    return aci_value

def compute_aei(y, sr, bands=10, band_width=100):
    # Evenness measures based on energy distribution across frequency bands
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=1024))
    S_db = librosa.amplitude_to_db(S, ref=np.max)
    total_energy = np.sum(S_db)
    freq_bins = np.linspace(0, sr // 2, S.shape[0])
    band_energies = [np.sum(S_db[(freq_bins >= i * band_width) & (freq_bins < (i + 1) * band_width)]) for i in range(bands)]
    aei_value = np.std(band_energies) / np.mean(band_energies) if np.mean(band_energies) != 0 else 0
    return 1 - aei_value if aei_value <= 1 else 0  # Normalized to [0,1]

def compute_bi(y, sr, freq_low=2000, freq_high=8000):
    # Bioacoustic Index based on frequencies within designated range
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=1024))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bio_power = np.sum(S[(freqs >= freq_low) & (freqs <= freq_high)])
    total_power = np.sum(S)
    return bio_power / total_power if total_power > 0 else 0

def compute_ndsi(y, sr, bio_low=2000, bio_high=8000, anthro_low=0, anthro_high=200):
    # Calculate the NDSI: Ratio of biophony to anthrophony
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=1024))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bio_power = np.sum(S[(freqs >= bio_low) & (freqs <= bio_high)])
    anthro_power = np.sum(S[(freqs >= anthro_low) & (freqs <= anthro_high)])
    return (bio_power - anthro_power) / (bio_power + anthro_power) if (bio_power + anthro_power) > 0 else 0

def bioacoustic_analysis(audio_data, sr):
    adi = compute_adi(audio_data, sr)
    aci = compute_aci(audio_data, sr)
    aei = compute_aei(audio_data, sr)
    bi = compute_bi(audio_data, sr)
    ndsi = compute_ndsi(audio_data, sr)

    return {
        "ADI": adi,
        "ACI": aci,
        "AEI": aei,
        "BI": bi,
        "NDSI": ndsi
    }
