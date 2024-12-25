import unittest
import os
import sounddevice as sd
import soundfile as sf
import numpy as np
import pytest
import time
import asyncio
from app.service.pht import PHT
from app.service.audio_transcription import WhisperHandler, TranscriptionMode
from app.config import PLAY_HT_API_KEY, PLAY_HT_USER_ID

@pytest.mark.integration
@pytest.mark.asyncio
class TestPHTIntegration(unittest.TestCase):
    async def asyncSetUp(self):
        print("\nSetting up test...")
        self.pht = PHT()
        self.whisper = WhisperHandler(TranscriptionMode.HF.value, "large")
        
        # Create test_outputs directory in project root if it doesn't exist
        current_dir = os.path.dirname(os.path.dirname(__file__))
        print(f"Current directory: {current_dir}")
        self.output_dir = os.path.join(current_dir, 'test_outputs')
        print(f"Output directory will be: {self.output_dir}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Ensure required credentials are set
        self.assertTrue(PLAY_HT_API_KEY, 'PLAY_HT_API_KEY not set in config')
        self.assertTrue(PLAY_HT_USER_ID, 'PLAY_HT_USER_ID not set in config')
    
    def setUp(self):
        pass
    
    def select_microphone(self):
        """List available audio input devices and let user select one"""
        print("\nListing audio devices...")
        devices = sd.query_devices()
        input_devices = []
        
        print("\n" + "="*50)
        print("AVAILABLE INPUT DEVICES:")
        print("="*50)
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # This is an input device
                print(f"{i}: {device['name']}")
                input_devices.append(i)
        print("="*50)
        
        if not input_devices:
            raise RuntimeError("No input devices found!")
        
        print("\nWaiting for microphone selection...")
        while True:
            try:
                selection = input("\nSelect microphone by number: ")
                device_id = int(selection)
                if device_id in input_devices:
                    print(f"Selected device {device_id}")
                    return device_id
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a number.")
    
    @pytest.mark.asyncio
    async def test_full_flow_with_mic(self):
        """Integration test using microphone input for voice matching"""
        print("\nStarting test_full_flow_with_mic...")
        
        # First run the async setup
        await self.asyncSetUp()
        
        # Let user select microphone
        device_id = self.select_microphone()
        
        # Record audio from selected microphone
        duration = 5  # seconds
        sample_rate = 44100
        
        print("\n" + "="*50)
        print(f"Using device: {sd.query_devices(device_id)['name']}")
        print(f"Will record for {duration} seconds")
        print("="*50)
        
        input("\nPress Enter when ready to start recording...")
        print("Recording starts in:")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        print("Recording NOW! Speak...")
        
        try:
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                device=device_id
            )
            sd.wait()
            print("Recording complete!")
        except sd.PortAudioError as e:
            print(f"\nError recording audio: {e}")
            raise
        
        # Save recording temporarily
        temp_wav = os.path.join(self.output_dir, "recording.wav")
        print(f"\nSaving recording to: {temp_wav}")
        sf.write(temp_wav, recording, sample_rate)
        
        # Read the recorded audio
        with open(temp_wav, 'rb') as f:
            audio_input = bytearray(f.read())
        
        # Transcribe the audio using Whisper
        print("\nTranscribing audio...")
        transcribed_text = await self.whisper.transcribe_voice(audio_input, detect_language=True)
        print("\n" + "="*50)
        print(f"Transcribed text: {transcribed_text}")
        print("="*50)
        
        if not transcribed_text:
            raise RuntimeError("Failed to transcribe audio")
        
        # Generate TTS with the transcribed text
        print("\nGenerating TTS response...")
        result = await self.pht.text_to_speech(audio_input, transcribed_text)
        
        # Save the output
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_file = os.path.join(self.output_dir, f'tts_output_{timestamp}.mp3')
        print(f"\nSaving TTS output to: {output_file}")
        with open(output_file, 'wb') as f:
            f.write(result)
        
        print("\n" + "="*50)
        print("Test complete! Files saved:")
        print(f"Original recording: {temp_wav}")
        print(f"Generated TTS: {output_file}")
        print("="*50)
        
        # Verify the output
        self.assertTrue(os.path.exists(output_file))
        self.assertTrue(os.path.getsize(output_file) > 0) 