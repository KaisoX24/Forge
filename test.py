# from ingestion.doc_scraper import DocScraper
from ingestion.chunking import Chunker
from ingestion.embeddings import EmbeddingService
from pathlib import Path
# from sklearn.metrics.pairwise import cosine_similarity
from ingestion.vector_store import VectorStore

# # scrapper=DocScraper()
# # scrapper.run(["https://fastapi.tiangolo.com/python-types/"])
chunks=Chunker().chunk_directory(Path('raw_docs'))
embeddings=EmbeddingService()
embeddings=embeddings.embed(chunks)
# print(f'Total Chunks: {len(chunks)}')
# print(f'Total Embeddings: {len(embeddings)}')
# print(f'Type of Embeddings: {type(embeddings)}')
# print(f'Length of one Embedding: {len(embeddings[0])}')
# print(f'Embedding: {embeddings[0][:20]}')

# similarity=cosine_similarity(
#     [embeddings[0]],
#     [embeddings[1]]
# )
# print(similarity[0][0])

vector_store=VectorStore()
vector_store.add_documents(documents=chunks,embeddings=embeddings)
print(vector_store.vector_store._collection.count())