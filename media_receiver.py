import threading
from queue import Queue, Empty
from scapy.all import sniff, IP, UDP
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY, DG_LANGUAGE, DG_MODEL
from utils import logger

class MediaReceiver:
    def __init__(self, channel_id):
        self.channel_id = channel_id
        self.rtp_port = 0
        self.stop_flag = False
        self.dg_connection = None
        self.packets_received = 0
        self.audio_queue = Queue()
        self.processing_thread = None

    def start_deepgram(self):
        try:
            deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
            self.dg_connection = deepgram.listen.websocket.v("1")
            
            def on_transcript(client, result, **kwargs):
                try:
                    logger.info(f"[Channel {self.channel_id}] Result: {result}")
                    sentence = result.channel.alternatives[0].transcript
                    if sentence.strip():
                        logger.info(f"[Channel {self.channel_id}] Transcript: {sentence}")
                except (KeyError, AttributeError) as e:
                    logger.error(f"Error processing transcript: {e}")
                    logger.debug(f"Raw transcript data: {result}")

            def on_error(client, error, **kwargs):
                logger.error(f"Deepgram error for channel {self.channel_id}: {error}")
            
            def on_close(client, **kwargs):
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
                interim_results=True,
                punctuate=True
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

    def _process_audio_queue(self):
        while not self.stop_flag:
            try:
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                except Empty:
                    continue

                if self.dg_connection and audio_data:
                    try:
                        self.dg_connection.send(audio_data)
                    except Exception as e:
                        logger.error(f"Error sending audio to Deepgram: {e}")
                        self.reconnect_deepgram()
            except Exception as e:
                logger.error(f"Error in audio processing thread: {e}")

    def reconnect_deepgram(self):
        try:
            if self.dg_connection:
                self.dg_connection.finish()
            self.start_deepgram()
        except Exception as e:
            logger.error(f"Failed to reconnect to Deepgram: {e}")

    def run(self):
        try:
            logger.info(f"Started processing for channel {self.channel_id} on port {self.rtp_port}")

            def process_packet(packet):
                if self.stop_flag:
                    return True

                if packet.haslayer(IP) and packet.haslayer(UDP):
                    dst_port = packet[UDP].dport

                    if dst_port == self.rtp_port:
                        try:
                            audio_data = bytes(packet[UDP].payload)[12:]
                            if audio_data:
                                self.audio_queue.put(audio_data)
                                self.packets_received += 1
                                if self.packets_received % 100 == 0:
                                    logger.info(f"Processed {self.packets_received} packets for channel {self.channel_id}")
                        except Exception as e:
                            logger.error(f"Error processing packet: {e}")
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
            try:
                self.dg_connection.finish()
            except Exception as e:
                logger.error(f"Error closing Deepgram connection: {e}")

        self.dg_connection = None
