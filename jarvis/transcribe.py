# ─── streaming transcription with Vosk (always-warm) ─────────────────────
import json, numpy as np
from vosk import Model, KaldiRecognizer

RATE  = 16_000
CHUNK = 512

model = Model("model")                 # one-time load
rec   = KaldiRecognizer(model, RATE)   # persistent recogniser

# ----- simple silence-based stop (Phase-1) -------------------------------
RMS_THRESHOLD      = 900               # may tune per microphone
SILENCE_CHUNKS_END = int(1.2 * RATE / CHUNK)   # ≈1.2 s of quiet
MAX_CHUNKS         = int(6 * RATE / CHUNK)     # hard cap 6 s

def record_and_transcribe(stream):
    """Stream audio from shared PyAudio handle into Vosk until silence."""
    rec.Reset()
    silent = 0
    total  = 0

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rec.AcceptWaveform(data)       # feed recogniser continuously
        total += 1

        # RMS-based silence detection
        audio_i16 = np.frombuffer(data, dtype=np.int16)
        if audio_i16.size:
            rms = np.sqrt(np.mean(audio_i16.astype(np.float32)**2))
        else:
            rms = 0.0

        if rms < RMS_THRESHOLD:
            silent += 1
            if silent >= SILENCE_CHUNKS_END:
                break
        else:
            silent = 0

        if total >= MAX_CHUNKS:        # safety cap
            break

    result = json.loads(rec.FinalResult())
    return result.get("text", "").strip()
