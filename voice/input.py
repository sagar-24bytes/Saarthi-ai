# voice/input.py

import sounddevice as sd
import numpy as np
import queue
import time
import sys
import os
from scipy.io.wavfile import write
from faster_whisper import WhisperModel

print("Loading Whisper model...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("Whisper loaded.")

# ============================================================
# STANDARD RECORDING (For CLI / main.py)
# ============================================================

def record(seconds=5, filename="recorded.wav", device=None):
    fs = 16000
    print(f"Speak now (using device: {device})...")
    audio = sd.rec(int(seconds * fs), samplerate=fs, channels=1, device=device)
    sd.wait()
    write(filename, fs, audio)

def listen(seconds=5, device=None):
    record(seconds, device=device)
    try:
        segments, info = model.transcribe("recorded.wav", language="en")
        text = " ".join([seg.text for seg in segments])
        return text.strip()
    finally:
        # Session cleanup: remove temporary speech audio files
        if os.path.exists("recorded.wav"):
            try:
                os.remove("recorded.wav")
            except Exception:
                pass


# ============================================================
# INTERACTIVE RECORDING WITH AUTO-STOP (For GUI / gui.py)
# ============================================================

class InteractiveRecorder:
    def __init__(self, filename="recorded.wav", device=None, fs=16000):
        self.filename = filename
        self.device = device
        self.fs = fs
        self.q = queue.Queue()
        self.recording = False
        self.audio_data = []
        self.stream = None

    def record_audio(self, stop_event, status_cb=None):
        """
        Records audio until stop_event is set, silence is detected, or timeout occurs.
        Uses native hardware sample rates and channels to prevent DirectSound formatting errors,
        then resamples the output to 16000Hz mono.
        """
        self.audio_data = []
        self.recording = True
        
        # Audio threshold parameters
        silence_threshold = 0.010      # Lowered from 0.015 for higher microphone responsiveness
        silence_duration_limit = 5.0   # seconds of silence to trigger auto-stop
        no_speech_timeout = 10.0       # seconds to wait for speech to start
        
        speech_detected = False
        total_seconds = 0.0
        silence_seconds = 0.0
        
        # Query hardware defaults dynamically to prevent PaErrorCode -9999 (Format Not Supported)
        try:
            device_info = sd.query_devices(self.device, 'input')
            self.fs = int(device_info.get('default_samplerate', 16000))
            channels = int(device_info.get('max_input_channels', 1))
        except Exception as e:
            print(f"Error querying audio device properties: {e}", file=sys.stderr)
            self.fs = 16000
            channels = 1
            
        block_size = int(self.fs * 0.1)  # 100ms blocks
        
        # Define callback to extract mono channel from hardware input
        def callback_wrapper(indata, frames, time, status):
            if status:
                print(f"[sd status] {status}", file=sys.stderr)
            # Extract first channel (channel 0) to force mono format
            mono_data = indata[:, 0] if indata.ndim > 1 else indata
            self.q.put(mono_data.copy())

        # Open InputStream with automatic 1-retry fallback to improve reliability and reduce startup latency
        opened_successfully = False
        for attempt in range(2):
            try:
                self.stream = sd.InputStream(
                    samplerate=self.fs,
                    channels=channels,
                    device=self.device,
                    callback=callback_wrapper,
                    blocksize=block_size,
                    dtype='float32'
                )
                opened_successfully = True
                break
            except Exception as e:
                print(f"[WARNING] Microphone initialization attempt {attempt + 1} failed: {e}", file=sys.stderr)
                if attempt == 0:
                    time.sleep(0.5)  # Wait 500ms before retrying once
                    continue
                else:
                    print("[ERROR] Microphone initialization failed after retries.", file=sys.stderr)
                    return "error"

        try:
            with self.stream:
                # Active immediately notification
                if status_cb:
                    status_cb("[INFO] Microphone active. Please speak now...")
                
                while self.recording and not stop_event.is_set():
                    try:
                        # Get a 100ms chunk of audio
                        data = self.q.get(timeout=0.2)
                        self.audio_data.append(data)
                        
                        # Calculate RMS energy of this chunk
                        rms = np.sqrt(np.mean(data**2))
                        total_seconds += 0.1
                        
                        # Speech detection logic
                        if not speech_detected:
                            if rms > silence_threshold:
                                speech_detected = True
                                if status_cb:
                                    status_cb("[INFO] Speech detected. Recording...")
                            else:
                                if total_seconds >= no_speech_timeout:
                                    self.recording = False
                                    return "no_speech"
                        else:
                            if rms < silence_threshold:
                                silence_seconds += 0.1
                                if silence_seconds >= silence_duration_limit:
                                    if status_cb:
                                        status_cb("[INFO] Silence detected. Automatically stopping...")
                                    self.recording = False
                                    return "success"
                            else:
                                silence_seconds = 0.0
                                
                    except queue.Empty:
                        continue
                        
            return "success" if speech_detected else "no_speech"
            
        except Exception as e:
            print(f"Error in sounddevice InputStream: {e}", file=sys.stderr)
            return "error"
            
        finally:
            self.recording = False
            if self.stream:
                try:
                    self.stream.close()
                except Exception:
                    pass
                
            # Write WAV file if we gathered data
            if self.audio_data:
                try:
                    # Concatenate recorded mono blocks
                    audio_array = np.concatenate(self.audio_data, axis=0)
                    
                    # Software resampling to standard 16000 Hz mono (expected by Whisper)
                    target_fs = 16000
                    if self.fs != target_fs:
                        num_samples = int(len(audio_array) * target_fs / self.fs)
                        x_old = np.linspace(0, len(audio_array), len(audio_array))
                        x_new = np.linspace(0, len(audio_array), num_samples)
                        audio_array = np.interp(x_new, x_old, audio_array)
                    
                    write(self.filename, target_fs, audio_array)
                except Exception as e:
                    print(f"Error saving/resampling WAV file: {e}", file=sys.stderr)


def listen_interactive(stop_event, status_cb=None, device=None):
    """
    Records audio interactively. Handles timeouts and silence detection.
    Transcribes the audio using faster-whisper.
    Returns:
        tuple[str, str]: (result_code, text) where result_code is 'success', 'no_speech', or 'error'
    """
    recorder = InteractiveRecorder(device=device)
    result_code = recorder.record_audio(stop_event, status_cb)
    
    if result_code == "success":
        try:
            segments, info = model.transcribe("recorded.wav", language="en")
            text = " ".join([seg.text for seg in segments]).strip()
            return "success", text
        except Exception as e:
            print(f"Transcription error: {e}", file=sys.stderr)
            return "error", ""
        finally:
            # Session cleanup: remove temporary speech audio files after transcription
            if os.path.exists("recorded.wav"):
                try:
                    os.remove("recorded.wav")
                except Exception:
                    pass
    elif result_code == "no_speech":
        return "no_speech", ""
    else:
        return "error", ""
