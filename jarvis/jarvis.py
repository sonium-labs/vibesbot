"""
Main Jarvis voice assistant orchestrator.

This module coordinates the voice assistant's core functionality, including:
- Wake word detection
- Speech-to-text transcription
- Command interpretation
- Text-to-speech response
- Music control via REST API integration

The assistant maintains a single shared microphone stream for efficiency
and provides voice control over a remote music bot service.
"""

from wake_word import wait_for_wake_word
from transcribe import record_and_transcribe
from pynput.keyboard import Controller
from dotenv import load_dotenv
import pyttsx3, requests, pyaudio, os, time

# Initialize environment variables and global service objects
load_dotenv()                                 # Load configuration from .env file
keyboard = Controller()                       # For potential keyboard control
tts_engine = pyttsx3.init()                  # Text-to-speech engine

# Music bot configuration from environment
guild_id = os.getenv("GUILD_ID")             # Discord server ID
user_id = os.getenv("USER_ID")               # User's Discord ID
voice_channel_id = os.getenv("VOICE_CHANNEL_ID")  # Target voice channel

def speak(text: str):
    """
    Synthesize and play text as speech.
    
    Args:
        text: String to be spoken by the text-to-speech engine
    """
    tts_engine.say(text)
    tts_engine.runAndWait()

# Configure and initialize shared audio input stream
RATE = 16_000                                # Sample rate in Hz
CHUNK = 512                                  # Buffer size (matches Porcupine)
_pa = pyaudio.PyAudio()
shared_stream = _pa.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

def send_play_command(song_name: str):
    """
    Send request to music bot to play a specific song.

    Args:
        song_name: Name/query of the song to play

    Returns:
        dict: Response from the music bot API, or None on failure
    """
    url = "https://vibesbot.no-vibes.com/command/play"
    payload = {
        "guildId": guild_id,
        "userId": user_id,
        "voiceChannelId": voice_channel_id,
        "options": {"query": song_name}
    }
    try:
        return requests.post(url, json=payload).json()
    except Exception as e:
        print("Play request failed:", e)

def send_command(command: str):
    """
    Send a control command to the music bot.

    Args:
        command: Command name (e.g., 'pause', 'resume', 'stop')

    Returns:
        dict: Response from the music bot API, or None on failure
    """
    url = f"https://vibesbot.no-vibes.com/command/{command}"
    payload = {
        "guildId": guild_id,
        "userId": user_id,
        "voiceChannelId": voice_channel_id,
        "options": {}
    }
    try:
        return requests.post(url, json=payload).json()
    except Exception as e:
        print("Command request failed:", e)

def listen_for_voice_commands():
    """
    Main voice command loop.
    
    Continuously listens for wake word, transcribes subsequent speech,
    interprets commands, and executes appropriate actions. Supports
    music playback control and self-termination commands.
    """
    while True:
        print('Say "Jarvis" to wake...')
        wait_for_wake_word(shared_stream)           # Wait for activation
        print("Wake word detected.")
        transcript = record_and_transcribe(shared_stream)
        print(f"You said: {transcript}")

        # Command interpretation and execution
        if ("now" in transcript and "playing" in transcript):
            speak("Now playing.")
            send_command("now-playing")
        elif "played" in transcript:
            # Handle alternative phrasing for play command
            song = transcript.replace("played", "", 1).strip()
            if song:
                speak(f"Playing {song}")
                send_play_command(song)
        elif "play" in transcript:
            song = transcript.replace("play", "", 1).strip()
            if song:
                speak(f"Playing {song}")
                send_play_command(song)
        # Basic playback controls
        elif "stop"   in transcript: speak("Stopping.");  send_command("stop")
        elif "pause"  in transcript: speak("Pausing.");   send_command("pause")
        elif "resume" in transcript: speak("Resuming.");  send_command("resume")
        elif "next"   in transcript: speak("Skipping.");  send_command("next")
        elif "clear"  in transcript: speak("Clearing.");  send_command("clear")
        # Exit commands
        elif ("kill" in transcript and "self" in transcript) or \
             ("self" in transcript and "destruct" in transcript):
            speak("Goodbye.")
            break
        else:
            speak("Sorry, I didn't understand that command.")

def main():
    """
    Entry point: Initialize and run the voice assistant.
    
    Ensures proper cleanup of audio resources on exit.
    """
    try:
        print("Starting Jarvis...")
        listen_for_voice_commands()
    finally:
        # Clean up audio resources
        shared_stream.close()
        _pa.terminate()

if __name__ == "__main__":
    main()
