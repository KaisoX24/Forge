from ingestion.doc_scraper import DocScraper
from ingestion.chunking import Chunker
from ingestion.embeddings import EmbeddingService
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
from ingestion.vector_store import VectorStore

# scrapper=DocScraper()
# scrapper.run(["https://fastapi.tiangolo.com/python-types/"])
chunks=Chunker().chunk_directory(Path('raw_docs'))
embeddings=EmbeddingService()
embeddings=embeddings.embed(chunks)
print(f'Total Chunks: {len(chunks)}')
print(f'Total Embeddings: {len(embeddings)}')
print(f'Type of Embeddings: {type(embeddings)}')
print(f'Length of one Embedding: {len(embeddings[0])}')
print(f'Embedding: {embeddings[0][:20]}')

similarity=cosine_similarity(
    [embeddings[0]],
    [embeddings[1]]
)
print(similarity[0][0])

vector_store=VectorStore()
vector_store.add_documents(documents=chunks,embeddings=embeddings)
print(vector_store.vector_store._collection.count())

# from retrieval.retriever import Retriever

# retriver=Retriever()
# queries = [
#     # Directly relevant
#     "What is a type annotation in Python?",

#     # Irrelevant
#     "How do I configure Redis caching in FastAPI?",

#     # Indirectly relevant
#     "How can I tell Python what kind of value a function expects?",

#     # Weakly related
#     "How does FastAPI validate incoming data?",

#     # Specific relevant
#     "How do I define a dictionary with typed keys and values?",

#     # Irrelevant
#     "How do I add authentication to a FastAPI application?",

#     # Indirectly relevant
#     "Can a Python value have more than one possible type?",

#     # Irrelevant
#     "How do I deploy my FastAPI application using Kubernetes?",

#     # Specific relevant
#     "What does Annotated do in Python type hints?",

#     # Weakly related
#     "How do I create a POST endpoint in FastAPI?",

#     # Relevant
#     "How do generic types work with collections in Python?",

#     # Irrelevant
#     "How can I connect FastAPI to a MySQL database?",

#     # Indirectly relevant
#     "How do I specify that a parameter can be None?",

#     # Weakly related
#     "How does FastAPI provide editor support?",

#     # Irrelevant
#     "How do I implement JWT tokens for FastAPI users?",

#     # Specific relevant
#     "How do I annotate a tuple containing different data types?",

#     # Relevant but phrased differently
#     "What standard Python types are supported by type annotations?",

#     # Irrelevant
#     "How do I handle file uploads in FastAPI?",

#     # Potentially tricky
#     "Why would I use type hints when writing FastAPI code?",

#     # Definitely outside this document
#     "How do I configure WebSocket communication in FastAPI?",
# ]
# for query in queries:
#     results = retriver.retrieve(query)

#     print(f"\nQUERY: {query}")
#     if not any(results):
#         print("Irrelevant to the Data")
#         continue
#     for _, distance in results:
#         print(f"{distance:.3f}")

#     print("-" * 70)
