import os
import sys

class SuppressCStderr:
    def __enter__(self):
        self.stderr_fd = sys.stderr.fileno()

        # Save a copy of the original stderr
        self.saved_stderr_fd = os.dup(self.stderr_fd)

        # Open /dev/null and redirect stderr to it
        self.devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.devnull_fd, self.stderr_fd)

        return self  # <--- needed for context managers

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore original stderr
        os.dup2(self.saved_stderr_fd, self.stderr_fd)
        os.close(self.devnull_fd)
        os.close(self.saved_stderr_fd)

from vosk import Model, KaldiRecognizer
import pyaudio
import wave
import json
import numpy as np

def record_and_transcribe():
    print("[TRANSCRIBE DEBUG] record_and_transcribe: Function entered")
    RATE = 16000
    CHUNK = 1024 
    WAVE_OUTPUT_FILENAME = "temp.wav"
    SILENCE_THRESHOLD = 900  # RMS threshold for silence
    MIN_SILENCE_DURATION_SEC = 1.5  # Seconds of silence to stop recording
    MAX_RECORDING_DURATION_SEC = 7.0  # Max seconds to record
    POST_SILENCE_BUFFER_SEC = 0.4  # Add this line

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("[TRANSCRIBE DEBUG] Starting recording with parameters:")
    print(f"[TRANSCRIBE DEBUG] SILENCE_THRESHOLD: {SILENCE_THRESHOLD}")
    print(f"[TRANSCRIBE DEBUG] MIN_SILENCE_DURATION_SEC: {MIN_SILENCE_DURATION_SEC}")
    
    frames = []
    silent_chunks = 0
    total_chunks = 0
    min_silent_chunks_to_stop = int(MIN_SILENCE_DURATION_SEC * RATE / CHUNK)
    max_chunks_to_record = int(MAX_RECORDING_DURATION_SEC * RATE / CHUNK)
    post_silence_chunks = int(POST_SILENCE_BUFFER_SEC * RATE / CHUNK)
    post_silence_counter = 0
    silence_triggered = False

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        total_chunks += 1

        # Calculate RMS of the current chunk
        audio_data = np.frombuffer(data, dtype=np.int16)
        if audio_data.size > 0:
            audio_data_float = audio_data.astype(np.float32) # Cast to float32 before squaring
            mean_sq = np.mean(audio_data_float**2)
            if mean_sq >= 0:
                rms = np.sqrt(mean_sq)
            else:
                rms = 0 # Should not happen with squared values, but as a safeguard
        else:
            rms = 0 # Treat empty chunk as silence

        print(f"[TRANSCRIBE DEBUG] RMS: {rms:.2f}, Silent chunks: {silent_chunks}/{min_silent_chunks_to_stop}")

        if not silence_triggered:
            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
                print(f"[TRANSCRIBE DEBUG] Silence detected ({silent_chunks}/{min_silent_chunks_to_stop})")
            else:
                if silent_chunks > 0:
                    print("[TRANSCRIBE DEBUG] Resetting silence counter due to sound")
                silent_chunks = 0

            if silent_chunks >= min_silent_chunks_to_stop:
                print(f"Detected {MIN_SILENCE_DURATION_SEC}s of silence. Starting post-silence buffer.")
                silence_triggered = True
                post_silence_counter = 0
        else:
            post_silence_counter += 1
            if post_silence_counter >= post_silence_chunks:
                print(f"[TRANSCRIBE DEBUG] Post-silence buffer complete. Stopping recording.")
                break

        if total_chunks >= max_chunks_to_record:
            print(f"[TRANSCRIBE DEBUG] Max duration reached ({MAX_RECORDING_DURATION_SEC}s). Stopping.")
            break

    print("[TRANSCRIBE DEBUG] Recording finished. Processing audio...")
    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(1)
    # Use a fixed sample width (2 bytes for paInt16) as p is terminated
    wf.setsampwidth(2) 
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    print("[TRANSCRIBE DEBUG] WAV file saved.")

    print("[TRANSCRIBE DEBUG] Starting transcription with Vosk...")

    with SuppressCStderr():
        model = Model("model")
        rec = KaldiRecognizer(model, RATE)

        wf = wave.open(WAVE_OUTPUT_FILENAME, "rb")
        results = []

        while True:
            data = wf.readframes(CHUNK)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                results.append(result.get("text", ""))

    final_text = " ".join(results).strip()
    return final_text

if __name__ == "__main__":
    text = record_and_transcribe()
    print(f"You said: {text}")
