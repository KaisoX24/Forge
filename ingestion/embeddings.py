from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document


class EmbeddingService:
    def __init__(self,model: str = "nomic-embed-text",base_url: str = "http://localhost:11434"):
        self.embeddings = OllamaEmbeddings(
            model=model,
            base_url=base_url)

    def embed(self, documents: list[Document]) -> list[list[float]]:
        texts = [document.page_content for document in documents]

        return self.embeddings.embed_documents(texts)

    def embed_query(self,query:str)->list[list[float]]:
        return self.embeddings.embed_query(query.strip())