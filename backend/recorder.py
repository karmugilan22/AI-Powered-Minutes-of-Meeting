import os
import threading
import time
import wave
import logging

logger = logging.getLogger("mom_assistant.recorder")

# Try importing sounddevice and numpy/scipy. If they fail, we fall back to a mock recorder.
SOUNDDEVICE_AVAILABLE = False
try:
    import sounddevice as sd
    import numpy as np
    import scipy.io.wavfile as wav
    SOUNDDEVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"SoundDevice or SciPy/NumPy not available. Server-side recording will be disabled: {e}")

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.device_id = None
        self.sample_rate = 16000  # 16kHz is ideal for Speech-to-Text
        self.channels = 1
        self.frames = []
        self.thread = None
        self.start_time = None
        self.duration = 0
        self.output_filepath = None

    def get_input_devices(self):
        if not SOUNDDEVICE_AVAILABLE:
            return []
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, d in enumerate(devices):
                if d.get('max_input_channels', 0) > 0:
                    input_devices.append({
                        "id": i,
                        "name": d.get('name', f"Device {i}"),
                        "max_input_channels": d.get('max_input_channels'),
                        "default_samplerate": d.get('default_samplerate')
                    })
            return input_devices
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
            return []

    def _record_loop(self):
        try:
            self.frames = []
            # We record in blocks/chunks to allow pausing/stopping cleanly
            block_duration = 0.5  # half-second blocks
            block_size = int(self.sample_rate * block_duration)
            
            # sounddevice InputStream
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device_id,
                dtype='int16'
            ) as stream:
                while self.is_recording:
                    # Read audio block
                    data, overflowed = stream.read(block_size)
                    if overflowed:
                        logger.warning("Audio input overflowed")
                    self.frames.append(data.copy())
                    self.duration = int(time.time() - self.start_time)
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            self.is_recording = False

    def start_recording(self, output_filepath, device_id=None):
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("SoundDevice library not available. Server-side recording is disabled.")
            
        if self.is_recording:
            return False

        self.output_filepath = output_filepath
        self.device_id = device_id
        self.is_recording = True
        self.start_time = time.time()
        self.duration = 0
        
        # Make sure directory exists
        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

        self.thread = threading.Thread(target=self._record_loop)
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop_recording(self):
        if not self.is_recording:
            return 0
            
        self.is_recording = False
        if self.thread:
            self.thread.join(timeout=3)
            
        if not self.frames:
            return 0

        # Save to WAV file
        try:
            audio_data = np.concatenate(self.frames, axis=0)
            
            with wave.open(self.output_filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
                
            return self.duration
        except Exception as e:
            logger.error(f"Error saving recorded WAV file: {e}")
            return 0

# Global recorder instance
recorder = AudioRecorder()
