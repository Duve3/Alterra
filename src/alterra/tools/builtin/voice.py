"""Voice control tools."""

from pydantic import BaseModel, Field

from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...voice.pipeline import VoicePipeline
from ..base import Tool, ToolContext


class VoiceListenArguments(BaseModel):
    duration: float = Field(
        default=10.0, gt=0, le=300, description="Maximum listening duration in seconds"
    )


class VoiceListenTool(Tool):
    name = "voice.listen"
    description = "Start listening for voice input for a specified duration"
    arguments_model = VoiceListenArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=300)

    def __init__(self, pipeline: VoicePipeline) -> None:
        self._pipeline = pipeline

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        args = VoiceListenArguments.model_validate(arguments.model_dump())
        if not self._pipeline.is_running:
            await self._pipeline.start()
        return {
            "status": "listening",
            "duration": args.duration,
            "message": f"Listening for {args.duration} seconds...",
        }


class VoiceStopArguments(BaseModel):
    pass


class VoiceStopTool(Tool):
    name = "voice.stop"
    description = "Stop the voice pipeline"
    arguments_model = VoiceStopArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.NONE, timeout_seconds=5)

    def __init__(self, pipeline: VoicePipeline) -> None:
        self._pipeline = pipeline

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        if self._pipeline.is_running:
            await self._pipeline.stop()
        return {"status": "stopped", "message": "Voice pipeline stopped"}


class VoiceSpeakArguments(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="Text to speak")
    voice: str | None = Field(default=None, description="Voice to use (if supported by TTS)")


class VoiceSpeakTool(Tool):
    name = "voice.speak"
    description = "Speak text using TTS"
    arguments_model = VoiceSpeakArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=30)

    def __init__(self, pipeline: VoicePipeline) -> None:
        self._pipeline = pipeline

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        args = VoiceSpeakArguments.model_validate(arguments.model_dump())
        await self._pipeline.speak(args.text, args.voice)
        return {"status": "spoken", "text": args.text}


class VoiceStatusArguments(BaseModel):
    pass


class VoiceStatusTool(Tool):
    name = "voice.status"
    description = "Get the current voice pipeline status"
    arguments_model = VoiceStatusArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.NONE, timeout_seconds=5)

    def __init__(self, pipeline: VoicePipeline) -> None:
        self._pipeline = pipeline

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        return {
            "running": self._pipeline.is_running,
            "state": self._pipeline.state.value,
            "config": {
                "sample_rate": self._pipeline._config.sample_rate,
                "channels": self._pipeline._config.channels,
                "vad_silence_timeout": self._pipeline._config.vad_silence_timeout,
                "max_speech_duration": self._pipeline._config.max_speech_duration,
            },
        }
