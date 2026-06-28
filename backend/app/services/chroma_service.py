import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from ..config import settings

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

# Get or create a collection
collection = chroma_client.get_or_create_collection(name="places_collection")

# Initialize SentenceTransformer embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def add_document(doc_id: str, text: str, metadata: dict):
    """Embeds and upserts a document to ChromaDB."""
    embedding = embedding_model.encode(text).tolist()
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata]
    )

def query_documents(query_text: str, n_results: int = 1) -> list:
    """Queries ChromaDB for similar documents."""
    query_embedding = embedding_model.encode(query_text).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    return results
