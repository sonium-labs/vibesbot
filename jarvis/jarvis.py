# ─── high-level orchestrator ──────────────────────────────────────────────
from wake_word import wait_for_wake_word
from transcribe import record_and_transcribe
from pynput.keyboard import Controller
from dotenv import load_dotenv
import pyttsx3, requests, pyaudio, os, time

# ─── env & global objects ────────────────────────────────────────────────
load_dotenv()                                 # one-time load
keyboard  = Controller()
tts_engine = pyttsx3.init()

guild_id         = os.getenv("GUILD_ID")
user_id          = os.getenv("USER_ID")
voice_channel_id = os.getenv("VOICE_CHANNEL_ID")

def speak(text: str):
    tts_engine.say(text)
    tts_engine.runAndWait()

# ─── single open microphone stream ───────────────────────────────────────
RATE  = 16_000
CHUNK = 512                                   # Porcupine frame length
_pa = pyaudio.PyAudio()
shared_stream = _pa.open(format=pyaudio.paInt16,
                         channels=1,
                         rate=RATE,
                         input=True,
                         frames_per_buffer=CHUNK)

# ─── REST helpers (unchanged) ────────────────────────────────────────────
def send_play_command(song_name: str):
    url = "https://vibesbot.no-vibes.com/command/play"
    payload = {"guildId": guild_id,
               "userId": user_id,
               "voiceChannelId": voice_channel_id,
               "options": {"query": song_name}}
    try:
        return requests.post(url, json=payload).json()
    except Exception as e:
        print("Play request failed:", e)

def send_command(command: str):
    url = f"https://vibesbot.no-vibes.com/command/{command}"
    payload = {"guildId": guild_id,
               "userId": user_id,
               "voiceChannelId": voice_channel_id,
               "options": {}}
    try:
        return requests.post(url, json=payload).json()
    except Exception as e:
        print("Command request failed:", e)

# ─── main voice loop ─────────────────────────────────────────────────────
def listen_for_voice_commands():
    while True:
        print('Say "Jarvis" to wake...')
        wait_for_wake_word(shared_stream)           # <─ shared stream
        print("Wake word detected.")
        transcript = record_and_transcribe(shared_stream)  # "
        print(f"You said: {transcript}")

        if ("now" in transcript and "playing" in transcript):
            speak("Now playing.");                  send_command("now-playing")
        elif "played" in transcript:
            song = transcript.replace("played", "", 1).strip()
            if song: speak(f"Playing {song}");       send_play_command(song)
        elif "play" in transcript:
            song = transcript.replace("play", "", 1).strip()
            if song: speak(f"Playing {song}");       send_play_command(song)
        elif "stop"   in transcript: speak("Stopping.");  send_command("stop")
        elif "pause"  in transcript: speak("Pausing.");   send_command("pause")
        elif "resume" in transcript: speak("Resuming.");  send_command("resume")
        elif "next"   in transcript: speak("Skipping.");  send_command("next")
        elif "clear"  in transcript: speak("Clearing.");  send_command("clear")
        elif ("kill" in transcript and "self" in transcript) or \
             ("self" in transcript and "destruct" in transcript):
            speak("Goodbye.")
            break
        else:
            speak("Sorry, I didn't understand that command.")

def main():
    try:
        print("Starting Jarvis...")
        listen_for_voice_commands()
    finally:
        shared_stream.close()
        _pa.terminate()

if __name__ == "__main__":
    main()
