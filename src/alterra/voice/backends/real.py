"""Real voice backends using faster-whisper, Piper, Silero VAD, openWakeWord, and sounddevice."""

from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

from ..core import (
    AudioBackend,
    AudioChunk,
    AudioPlayer,
    STTBackend,
    TTSBackend,
    TranscriptionResult,
    VADBackend,
    VADResult,
    WakeWordBackend,
    WakeWordResult,
)


class FasterWhisperSTT(STTBackend):
    """faster-whisper STT backend."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        download_root: Optional[str] = None,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._download_root = download_root
        self._model = None
        self._running = False

    @property
    def name(self) -> str:
        return f"faster-whisper-{self._model_size}"

    async def start(self) -> None:
        if self._running:
            return
        # Load model in thread pool to avoid blocking
        from faster_whisper import WhisperModel

        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            lambda: WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=self._download_root,
            ),
        )
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._model = None

    async def transcribe(
        self, audio: bytes, sample_rate: int, channels: int
    ) -> TranscriptionResult:
        if not self._running:
            await self.start()

        # Write audio to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            with wave.open(f, "wb") as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)
                wav.writeframes(audio)

        try:
            segments, info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._model.transcribe(temp_path, beam_size=5, language=None),
            )
            text = " ".join(segment.text for segment in segments).strip()
            return TranscriptionResult(
                text=text,
                confidence=info.language_probability if info else 0.0,
                language=info.language if info else None,
                duration_seconds=info.duration if info else 0.0,
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        # For streaming, accumulate chunks and transcribe periodically
        buffer = bytearray()
        sample_rate = 16000
        channels = 1
        chunk_duration = 0.0

        async for chunk in audio_stream:
            buffer.extend(chunk.data)
            chunk_duration += len(chunk.data) / (chunk.sample_rate * chunk.channels * 2)

            # Transcribe every ~2 seconds of audio
            if chunk_duration >= 2.0 and buffer:
                audio_bytes = bytes(buffer)
                buffer.clear()
                chunk_duration = 0.0

                result = await self.transcribe(audio_bytes, sample_rate, channels)
                if result.text:
                    yield result


class PiperTTS(TTSBackend):
    """Piper TTS backend."""

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        model_dir: Optional[str] = None,
        use_cuda: bool = False,
    ) -> None:
        self._voice = voice
        self._model_dir = Path(model_dir) if model_dir else None
        self._use_cuda = use_cuda
        self._piper = None
        self._running = False

    @property
    def name(self) -> str:
        return f"piper-{self._voice}"

    @property
    def sample_rate(self) -> int:
        return 22050  # Piper default

    @property
    def voices(self) -> list[str]:
        return [
            "en_US-lessac-medium",
            "en_US-lessac-low",
            "en_US-lessac-high",
            "en_US-ryan-medium",
            "en_US-ryan-low",
            "en_US-ryan-high",
            "en_US-amy-medium",
            "en_US-amy-low",
            "en_US-amy-high",
        ]

    async def start(self) -> None:
        if self._running:
            return
        from piper import PiperVoice

        loop = asyncio.get_event_loop()
        self._piper = await loop.run_in_executor(
            None,
            lambda: PiperVoice.load(
                model_path=str(self._model_dir / f"{self._voice}.onnx")
                if self._model_dir
                else self._voice,
                config_path=str(self._model_dir / f"{self._voice}.onnx.json")
                if self._model_dir
                else None,
                use_cuda=self._use_cuda,
            ),
        )
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._piper = None

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        if not self._running:
            await self.start()

        voice = voice or self._voice
        if self._piper is None:
            await self.start()

        # Use temporary file for synthesis
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._piper.synthesize(text, output_file=temp_path),
            )
            with open(temp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def synthesize_stream(
        self, text: str, voice: Optional[str] = None
    ) -> AsyncIterator[bytes]:
        # Piper doesn't easily support streaming, so synthesize full then chunk
        audio = await self.synthesize(text, voice)
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            yield audio[i : i + chunk_size]
            await asyncio.sleep(0.01)


class SileroVAD(VADBackend):
    """Silero VAD backend."""

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_duration_ms: int = 100,
        speech_pad_ms: int = 30,
    ) -> None:
        self._threshold = threshold
        self._min_silence_duration_ms = min_silence_duration_ms
        self._speech_pad_ms = speech_pad_ms
        self._model = None
        self._running = False

    @property
    def name(self) -> str:
        return "silero-vad"

    async def start(self) -> None:
        if self._running:
            return
        from silero_vad import load_silero_vad

        loop = asyncio.get_event_loop()
        self._model, _ = await loop.run_in_executor(
            None,
            lambda: load_silero_vad(),
        )
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._model = None

    async def process(self, chunk: AudioChunk) -> VADResult:
        if not self._running:
            await self.start()

        # Silero VAD expects 16kHz mono 16-bit PCM
        # Convert if needed
        import numpy as np

        audio_data = np.frombuffer(chunk.data, dtype=np.int16).astype(np.float32) / 32768.0

        # Resample if needed (simple approach - just use first channel if stereo)
        if chunk.channels > 1:
            audio_data = audio_data[:: chunk.channels]

        if chunk.sample_rate != 16000:
            # Simple resample - would need proper resampling in production
            import scipy.signal

            audio_data = scipy.signal.resample(
                audio_data,
                int(len(audio_data) * 16000 / chunk.sample_rate),
            )

        # Run VAD
        speech_prob = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._model(audio_data, chunk.sample_rate),
        )

        is_speech = speech_prob > self._threshold
        return VADResult(
            is_speech=is_speech,
            confidence=float(speech_prob),
        )


class OpenWakeWord(WakeWordBackend):
    """openWakeWord backend."""

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
    ) -> None:
        self._model_name = model_name
        self._threshold = threshold
        self._model = None
        self._running = False

    @property
    def name(self) -> str:
        return f"openwakeword-{self._model_name}"

    async def start(self) -> None:
        if self._running:
            return
        from openwakeword import Model

        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            lambda: Model(wakeword_models=[self._model_name]),
        )
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._model = None

    async def process(self, chunk: AudioChunk) -> WakeWordResult:
        if not self._running:
            await self.start()

        # openWakeWord expects 16kHz mono 16-bit PCM
        import numpy as np

        audio_data = np.frombuffer(chunk.data, dtype=np.int16).astype(np.float32) / 32768.0

        # Convert if needed
        if chunk.channels > 1:
            audio_data = audio_data[:: chunk.channels]

        if chunk.sample_rate != 16000:
            import scipy.signal

            audio_data = scipy.signal.resample(
                audio_data,
                int(len(audio_data) * 16000 / chunk.sample_rate),
            )

        # Run wake word detection
        predictions = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._model.predict(audio_data),
        )

        # Check if any model detected the wake word
        detected = False
        max_confidence = 0.0
        for model_name, prob in predictions.items():
            if prob > self._threshold:
                detected = True
                max_confidence = max(max_confidence, prob)

        return WakeWordResult(
            detected=detected,
            confidence=max_confidence,
            model_name=self._model_name,
        )


class SoundDeviceBackend(AudioBackend):
    """sounddevice-based audio I/O backend."""

    def __init__(
        self,
        input_device_index: Optional[int] = None,
        output_device_index: Optional[int] = None,
    ) -> None:
        self._input_device_index = input_device_index
        self._output_device_index = output_device_index
        self._input_stream = None
        self._output_stream = None
        self._running = False
        self._capture_queue: asyncio.Queue[AudioChunk] = asyncio.Queue()

    @property
    def name(self) -> str:
        return "sounddevice"

    async def start_capture(self, sample_rate: int, channels: int) -> AsyncIterator[AudioChunk]:
        import sounddevice as sd

        if self._running:
            return

        # Configure sounddevice
        sd.default.samplerate = sample_rate
        sd.default.channels = channels
        if self._input_device_index is not None:
            sd.default.device = (self._input_device_index, sd.default.device[1])

        self._running = True

        def callback(indata, frames, time, status):
            """sounddevice callback - runs in separate thread."""
            if status:
                pass  # Could log status
            if self._running:
                # Copy data to avoid buffer reuse issues
                audio_data = indata.copy()
                chunk = AudioChunk(
                    data=audio_data.tobytes(),
                    sample_rate=sample_rate,
                    channels=channels,
                )
                # Put in queue (non-blocking)
                try:
                    self._capture_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass  # Drop chunk if queue full

        # Start input stream
        self._input_stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            callback=callback,
            blocksize=int(sample_rate * 0.1),  # 100ms chunks
            device=self._input_device_index,
        )
        self._input_stream.start()
        self._running = True

        try:
            while self._running:
                try:
                    chunk = await asyncio.wait_for(self._capture_queue.get(), timeout=0.1)
                    yield chunk
                except asyncio.TimeoutError:
                    continue
        finally:
            if self._input_stream:
                self._input_stream.stop()
                self._input_stream.close()
                self._input_stream = None
            self._running = False
            # Clear queue
            while not self._capture_queue.empty():
                try:
                    self._capture_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def start_playback(self, sample_rate: int, channels: int) -> AudioPlayer:
        import sounddevice as sd

        if self._output_stream is not None:
            self._output_stream.stop()
            self._output_stream.close()

        if self._output_device_index is not None:
            sd.default.device = (sd.default.device[0], self._output_device_index)

        self._output_stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
        )
        self._output_stream.start()

        return SoundDevicePlayer(self._output_stream, sample_rate, channels)

    async def stop(self) -> None:
        self._running = False
        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None
        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None
        # Clear queue
        while not self._capture_queue.empty():
            try:
                self._capture_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class SoundDevicePlayer(AudioPlayer):
    """sounddevice playback controller."""

    def __init__(self, stream, sample_rate: int, channels: int) -> None:
        self._stream = stream
        self._sample_rate = sample_rate
        self._channels = channels
        self._stopped = False

    async def write(self, chunk: AudioChunk) -> None:
        if self._stopped:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._stream.write(chunk.data))

    async def flush(self) -> None:
        pass

    async def stop(self) -> None:
        self._stopped = True
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None