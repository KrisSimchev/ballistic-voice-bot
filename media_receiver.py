import threading
from queue import Queue, Empty
from scapy.all import sniff, IP, UDP
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY, DG_LANGUAGE, DG_MODEL
from utils import logger
import audioop
import noisereduce as nr
import numpy as np
import time
from conversation_handler import ConversationHandler
from tts_handler import TTSHandler

class MediaReceiver:
    def __init__(self, channel_id, openai_thread_id,  codec="PCMU"):
        self.channel_id = channel_id
        self.codec = codec 
        self.rtp_port = 0
        self.stop_flag = False
        self.dg_connection = None
        self.packets_received = 0
        self.audio_queue = Queue()
        self.processing_thread = None
        self.buffer = bytearray()
        self.CHUNK_SIZE = 1920  # 240 ms at 8kHz mono
        self.volume_multiplier = 1.85  # Slight volume boost
        self.conversation_handler = ConversationHandler(openai_thread_id, TTSHandler(channel_id))
        self.last_transcript_time = time.time()
        self.openai_thread_id = openai_thread_id
    
    def start_deepgram(self):
        try:
            deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
            self.dg_connection = deepgram.listen.websocket.v("1")
            
            def on_transcript(client, result, **kwargs):
                try:
                    sentence = result.channel.alternatives[0].transcript
                    if sentence.strip():
                        current_time = time.time()
                        logger.info(f"[Channel {self.channel_id}] Transcript: {sentence}")
                        
                        # Get AI response if appropriate
                        self.conversation_handler.handle_transcript(
                            sentence, 
                            current_time
                        )
                        
                        # logger.info(f"[Channel {self.channel_id}] Detected end of speech")
                        self.conversation_handler.generate_and_stream(current_time)
                            
                except (KeyError, AttributeError) as e:
                    logger.error(f"Error processing transcript: {e}")
            def on_error(client, error, **kwargs):
                logger.error(f"Deepgram error for channel {self.channel_id}: {error}")
            
            def on_close(client,**kwargs):
                logger.info(f"Deepgram connection closed for channel {self.channel_id}")
            
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)
            
            options = LiveOptions(
                language=DG_LANGUAGE,
                model=DG_MODEL,
                sample_rate=8000,
                encoding="linear16",
                channels=1,
                interim_results=False,
                endpointing=600,
            )
            
            if not self.dg_connection.start(options):
                logger.error("Failed to start Deepgram connection")
                return False
            
            self.processing_thread = threading.Thread(target=self._process_audio_queue)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            return True

        except Exception as e:
            logger.error(f"Deepgram setup failed for channel {self.channel_id}: {e}")
            return False

    def _decode_audio(self, raw_audio):
        """Decode audio from G.711 mu-law or A-law to linear PCM."""
        try:
            if self.codec == "PCMU":  # mu-law
                return audioop.ulaw2lin(raw_audio, 2)
            elif self.codec == "PCMA":  # A-law
                return audioop.alaw2lin(raw_audio, 2)
            else:
                logger.error(f"Unsupported codec: {self.codec}")
                return None
        except Exception as e:
            logger.error(f"Error decoding audio: {e}")
            return None

    def _process_audio_data(self, audio_data):
        """Preprocess audio data before sending to Deepgram."""
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # High-pass filter to remove low-frequency noise
            alpha = 0.95
            shifted = np.roll(audio_array, 1)
            highpassed = audio_array.astype(np.float32) - alpha * shifted.astype(np.float32)
            highpassed[0] = audio_array[0]  # Avoid initial jump
            audio_array = highpassed.astype(np.int16)

            # Noise reduction
            reduced_noise = nr.reduce_noise(y=audio_array, sr=8000, prop_decrease=0.7)

            # Convert back to bytes
            processed_data = reduced_noise.astype(np.int16).tobytes()

            # DC offset removal
            avg_val = audioop.avg(processed_data, 2)
            if avg_val != 0:
                processed_data = audioop.bias(processed_data, 2, -avg_val)

            # Dynamic gain control (AGC)
            target_rms = 1500
            current_rms = audioop.rms(processed_data, 2)
            if current_rms > 0:
                ratio = float(target_rms) / current_rms
                processed_data = audioop.mul(processed_data, 2, ratio)

            # Apply a slight volume boost after dynamic gain control
            processed_data = audioop.mul(processed_data, 2, self.volume_multiplier)

            return processed_data

        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
            return audio_data

    def _process_audio_queue(self):
        while not self.stop_flag:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if self.dg_connection and audio_data:
                    self.buffer.extend(audio_data)

                    while len(self.buffer) >= self.CHUNK_SIZE:
                        chunk = bytes(self.buffer[:self.CHUNK_SIZE])
                        self.buffer = self.buffer[self.CHUNK_SIZE:]

                        decoded_audio = self._decode_audio(chunk)
                        if decoded_audio:
                            processed_chunk = self._process_audio_data(decoded_audio)
                            self.dg_connection.send(processed_chunk)

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio processing thread: {e}")

    def run(self):
        try:
            logger.info(f"Started processing for channel {self.channel_id} on port {self.rtp_port}")

            def process_packet(packet):
                if self.stop_flag:
                    return True
                if packet.haslayer(IP) and packet.haslayer(UDP):
                    if packet[UDP].dport == self.rtp_port:
                        rtp_payload = bytes(packet[UDP].payload)[12:]  # Skip RTP header
                        if rtp_payload:
                            self.audio_queue.put(rtp_payload)
                            self.packets_received += 1
                            if self.packets_received % 100 == 0:
                                logger.info(f"Processed {self.packets_received} packets for channel {self.channel_id}")
                return False

            sniff(filter=f"udp port {self.rtp_port}", prn=process_packet, stop_filter=lambda x: self.stop_flag)

        except Exception as e:
            logger.error(f"Error in receiver for channel {self.channel_id}: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        logger.info(f"Cleaning up channel {self.channel_id}")
        self.stop_flag = True
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)
        if self.dg_connection:
            self.dg_connection.finish()
        self.dg_connection = None