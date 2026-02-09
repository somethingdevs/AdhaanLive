import wave
import os

def save_wav(path: str, audio_bytes: bytearray, sample_rate: int = 44100):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
