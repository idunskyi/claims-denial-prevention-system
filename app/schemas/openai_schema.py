from typing import List

from pydantic import BaseModel
from pydantic_ai import ModelRequest, ModelResponse, UserPromptPart, TextPart


class Message(BaseModel):
    content: str
    role: str


class OpenAIChatSchema(BaseModel):
    messages: List[Message]
    model: str

    def get_message(self) -> str:
        message = self.messages[-1]
        if message and message.role == "user":
            return message.content
        return ""

    def get_message_history(self) -> List[ModelRequest | ModelResponse]:
        message_history: List[ModelRequest | ModelResponse] = []

        for msg in self.messages[:-1]:
            content_text = msg.content or ""

            if msg.role == "user":
                message_history.append(
                    ModelRequest(parts=[UserPromptPart(content=content_text)])
                )
            elif msg.role == "assistant":
                message_history.append(
                    ModelResponse(parts=[TextPart(content=content_text)])
                )
            elif msg.role == "system":
                # treat system messages as part of the prompt
                message_history.append(
                    ModelRequest(parts=[UserPromptPart(content=content_text)])
                )

        return message_history
