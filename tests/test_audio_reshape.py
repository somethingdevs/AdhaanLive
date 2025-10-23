import numpy as np

from core.playback import reshape_audio_chunk


def test_mono_to_stereo_upmix():
    mono_data = np.array([100, -100, 50, -50], dtype=np.int16)
    frames = reshape_audio_chunk(mono_data, channels=2)
    assert frames.shape == (4, 2)
    assert np.all(frames[:, 0] == mono_data)
    assert np.all(frames[:, 1] == mono_data)


def test_stereo_pass_through():
    stereo_data = np.array([100, 200, -100, -200], dtype=np.int16)  # interleaved L R
    frames = reshape_audio_chunk(stereo_data, channels=2)
    assert frames.shape == (2, 2)
    assert frames[0, 0] == 100 and frames[0, 1] == 200
    assert frames[1, 0] == -100 and frames[1, 1] == -200
