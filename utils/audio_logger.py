# core/audio_logger.py
import os
import datetime
import subprocess
import numpy as np
import soundfile as sf
import logging

ASSETS_DIR = os.path.join(os.getcwd(), "assets", "audio_logs")
os.makedirs(ASSETS_DIR, exist_ok=True)


def record_audio_snippet(stream_url: str, duration: int = 10) -> str:
    """
    Records a short audio snippet from the livestream using ffmpeg.
    Returns the file path of the saved audio.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"adhaan_candidate_{timestamp}.wav"
    output_path = os.path.join(ASSETS_DIR, filename)

    try:
        cmd = [
            "ffmpeg", "-y", "-i", stream_url,
            "-t", str(duration),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "44100", "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"🎧 Saved audio snippet → {output_path}")
    except Exception as e:
        logging.error(f"❌ Failed to record audio snippet: {e}")
        output_path = "ERROR"

    return output_path


def compute_audio_metrics(file_path: str) -> dict:
    """
    Computes RMS and Peak levels (and dBFS equivalents) from a WAV file.
    """
    try:
        data, samplerate = sf.read(file_path)
        rms = np.sqrt(np.mean(np.square(data)))
        peak = np.max(np.abs(data))
        rms_db = 20 * np.log10(rms + 1e-9)
        peak_db = 20 * np.log10(peak + 1e-9)
        return {
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "rms_db": round(rms_db, 2),
            "peak_db": round(peak_db, 2)
        }
    except Exception as e:
        logging.error(f"❌ Failed to analyze audio file: {e}")
        return {"rms": None, "peak": None, "rms_db": None, "peak_db": None}
