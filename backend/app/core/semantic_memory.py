import google.generativeai as genai
from typing import List

class SemanticMemoryService:
    """
    Handles the generation of vector embeddings for text using Google's models.
    """
    def __init__(self, embedding_model: str = "models/gemini-embedding-2"):
        self.embedding_model = embedding_model

    async def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return []

        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            return result.get('embedding', [])
        except Exception as e:
            print(f"Embedding generation failed: {e}")
            return []

semantic_service = SemanticMemoryService()