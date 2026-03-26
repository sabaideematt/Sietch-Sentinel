"""ChromaDB backend — vector store for semantic search over past investigations."""

from __future__ import annotations

import logging
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


class ChromaBackend:
    """
    Vector store for semantic similarity search over investigation summaries.

    Uses ChromaDB with cosine distance and the default embedding function
    (or sentence-transformers when available).
    """

    def __init__(self, collection_name: str = "investigations"):
        self._collection_name = collection_name
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb

            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB collection '%s' initialized.", self._collection_name)
        except ImportError:
            logger.warning("chromadb not installed — vector search disabled.")
        except Exception as e:
            logger.warning("ChromaDB init failed: %s", e)
        return self._collection

    @property
    def available(self) -> bool:
        return self._get_collection() is not None

    def index(self, doc_id: str, text: str, metadata: Optional[dict] = None) -> bool:
        """Upsert a document into the vector store."""
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            coll.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata or {}],
            )
            return True
        except Exception as e:
            logger.error("ChromaDB upsert failed for '%s': %s", doc_id, e)
            return False

    def search(self, query: str, top_k: int = 5, where: Optional[dict] = None) -> list[tuple[str, float, dict]]:
        """
        Semantic search over indexed investigations.
        Returns list of (document_text, distance, metadata).
        """
        coll = self._get_collection()
        if coll is None:
            return []
        try:
            kwargs = {"query_texts": [query], "n_results": top_k}
            if where:
                kwargs["where"] = where
            results = coll.query(**kwargs)
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            return list(zip(docs, distances, metadatas))
        except Exception as e:
            logger.error("ChromaDB search failed: %s", e)
            return []

    def delete(self, doc_id: str) -> bool:
        coll = self._get_collection()
        if coll is None:
            return False
        try:
            coll.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error("ChromaDB delete failed for '%s': %s", doc_id, e)
            return False

    def count(self) -> int:
        coll = self._get_collection()
        if coll is None:
            return 0
        return coll.count()
