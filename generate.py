import os
import wave
import numpy as np
from elevenlabs import ElevenLabs
from config import ELEVEN_LABS_API_KEY, ELEVEN_LABS_VOICE_ID

# Define the Asterisk sounds directory for TTS
ASTERISK_SOUNDS_DIR = "/var/lib/asterisk/sounds/tts_audio"

def generate_tts_audio(text: str) -> bool:
    """
    Generate TTS audio using ElevenLabs and save it as a WAV file in the Asterisk sounds directory.
    
    Args:
        text (str): The text to convert to speech
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create filename based on the text
        filename = f"start_message.wav"
        full_path = os.path.join(ASTERISK_SOUNDS_DIR, filename)
        
        # Create directory if it doesn't exist
        os.makedirs(ASTERISK_SOUNDS_DIR, exist_ok=True)
        
        # Initialize ElevenLabs client
        client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)
        
        # Generate audio
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=ELEVEN_LABS_VOICE_ID,
            model_id="eleven_flash_v2_5",
            output_format="pcm_8000",
            language_code="bg"
        )
        
        # Combine all audio chunks
        audio_data = b''.join(chunk for chunk in audio_generator)
        
        # Convert to NumPy int16
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Increase volume (same as original implementation)
        audio_array = np.clip(audio_array * 2.0, -32768, 32767).astype(np.int16)
        
        # Write WAV file
        with wave.open(full_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(audio_array.tobytes())
            
        print(f"Successfully generated WAV file: {full_path}")
        return True
        
    except Exception as e:
        print(f"Error generating TTS audio: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    text = "Здравейте, с какво мога да Ви помогна днес?"
    generate_tts_audio(text) 
