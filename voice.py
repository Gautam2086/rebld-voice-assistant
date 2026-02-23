import io
import struct
import sys

import numpy as np
import sounddevice as sd

from config import settings


def record_audio() -> bytes:
    """Record audio from mic until Enter is pressed. Returns WAV bytes."""
    print("  🎙️  Recording... (press Enter to stop)")

    frames: list[np.ndarray] = []
    recording = True

    def callback(indata, frame_count, time_info, status):
        if recording:
            frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=settings.sample_rate,
        channels=1,
        dtype="int16",
        callback=callback,
    )

    stream.start()
    input()  # block until Enter
    recording = False
    stream.stop()
    stream.close()

    if not frames:
        return b""

    audio = np.concatenate(frames)
    return _numpy_to_wav(audio, settings.sample_rate)


def play_audio(mp3_bytes: bytes) -> None:
    """Play MP3 bytes through speakers using pydub + sounddevice."""
    from pydub import AudioSegment

    seg = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32)

    # handle stereo
    if seg.channels == 2:
        samples = samples.reshape((-1, 2))

    samples = samples / (2**15)  # normalize int16 -> float32
    sd.play(samples, samplerate=seg.frame_rate)
    sd.wait()


def _numpy_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert int16 numpy array to WAV bytes."""
    buf = io.BytesIO()
    num_samples = len(audio)
    data_size = num_samples * 2  # int16 = 2 bytes

    # WAV header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))       # chunk size
    buf.write(struct.pack("<H", 1))        # PCM
    buf.write(struct.pack("<H", 1))        # mono
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))  # byte rate
    buf.write(struct.pack("<H", 2))        # block align
    buf.write(struct.pack("<H", 16))       # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(audio.tobytes())

    return buf.getvalue()
