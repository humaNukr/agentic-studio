from typing import List, Dict
from app.models.schemas import Message

class MemoryManager:
    """
    Manages short-term conversation history in RAM.
    """
    def __init__(self):
        # Private dictionary to store sessions.
        # Key: session_id (str), Value: list of Messages
        self._storage: Dict[str, List[Message]] = {}

    def add_message(self, session_id: str, message: Message) -> None:
        """
        Adds a new message to the specified session.
        """
        if session_id not in self._storage:
            self._storage[session_id] = []
        self._storage[session_id].append(message)

    def get_context(self, session_id: str) -> List[Message]:
        """
        Retrieves the entire message history for a session.
        Returns an empty list if the session does not exist.
        """
        return self._storage.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """
        Deletes a session from memory to free up RAM.
        """
        if session_id in self._storage:
            del self._storage[session_id]