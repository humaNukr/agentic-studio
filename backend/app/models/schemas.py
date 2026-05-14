from pydantic import BaseModel, Field

class Message(BaseModel):
    """
    Data Transfer Object for a single chat message.
    """
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")
    content: str = Field(..., description="The actual text content of the message")

class ChatRequest(BaseModel):
    """
    Data Transfer Object for incoming chat requests from the client.
    """
    session_id: str = Field(..., description="Unique identifier for the chat session")
    prompt: str = Field(..., description="User input text")