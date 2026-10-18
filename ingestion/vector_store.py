from langchain_chroma import Chroma
from langchain_core.documents import Document
from pathlib import Path

class VectorStore:
    def __init__(self,collection_name:str="forge_documents",dir_path:Path=Path(__file__).parent.parent/'data'/'chroma'):
        self.vector_store=Chroma(
            collection_name=collection_name,
            persist_directory=dir_path)

    def add_documents(self,documents:list[Document],embeddings:list[list[float]]):
        ids=[doc.metadata['chunk_id'] for doc in documents]
        content=[doc.page_content for doc in documents]
        metadatas=[doc.metadata for doc in documents]

        self.vector_store._collection.add(
            ids=ids,
            documents=content,
            metadatas=metadatas,
            embeddings=embeddings
        )

    def similarity_search(self,query_vec:list[float],top_k:int=5):
        return self.vector_store.similarity_search_by_vector_with_relevance_scores(
            query_vec,k=top_k)
