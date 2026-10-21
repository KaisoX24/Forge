from ingestion.embeddings import EmbeddingService
from ingestion.vector_store import VectorStore
from models.data_models import RetrievedDocument

class Retriever:
    def __init__(self,embedding_service:EmbeddingService=EmbeddingService(),vector_store:VectorStore=VectorStore(),distance_threshold:float=0.75):
        self.embedding_service=embedding_service
        self.vector_store=vector_store
        self.distance_threshold=distance_threshold

    def retrieve(self,query:str,top_k:int=5)->list[RetrievedDocument]:
        query_vec=self.embedding_service.embed_query(query)
        results=self.vector_store.similarity_search(query_vec,top_k)
        return [RetrievedDocument(content=doc.page_content,metadata=doc.metadata,distance=score)
                for doc,score in results
                if score<=self.distance_threshold]