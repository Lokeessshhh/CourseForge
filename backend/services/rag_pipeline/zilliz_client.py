"""
Zilliz Cloud (Milvus) client for vector search.
Handles connection and search operations.
"""
import os
import logging
import json
from typing import List, Dict, Any, Optional

from pymilvus import connections, Collection, utility

logger = logging.getLogger(__name__)

class ZillizClient:
    """Singleton-style client for Zilliz Cloud operations."""
    
    def __init__(self):
        self.uri = os.environ.get("ZILLIZ_URI")
        self.token = os.environ.get("ZILLIZ_TOKEN")
        self.collection_name = os.environ.get("ZILLIZ_COLLECTION", "course_chunks")
        self._connected = False
        self._collection = None

    def connect(self):
        """Establish connection to Zilliz Cloud."""
        if self._connected:
            return True
            
        if not self.uri or not self.token:
            logger.error("ZILLIZ_URI or ZILLIZ_TOKEN not configured.")
            return False

        try:
            connections.connect("default", uri=self.uri, token=self.token)
            if self.collection_name in utility.list_collections():
                self._collection = Collection(name=self.collection_name)
                self._collection.load()
                self._connected = True
                logger.info(f"Connected to Zilliz collection '{self.collection_name}'.")
                return True
            else:
                logger.error(f"Collection '{self.collection_name}' not found.")
                return False
        except Exception as e:
            logger.exception(f"Failed to connect to Zilliz Cloud: {e}")
            return False

    def search(
        self, 
        query_vector: List[float], 
        top_k: int = 20, 
        filter_expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search.
        Returns a list of dicts with entity data.
        """
        if not self._connected:
            if not self.connect():
                return []

        if output_fields is None:
            # Default fields to retrieve based on our schema
            output_fields = [
                "id", "doc_id", "document_id", "content", "chunk_index", 
                "level", "parent_id", "meta_json", "created_at"
            ]

        try:
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            results = self._collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=output_fields
            )

            # Parse results
            hits = []
            for hits_in_batch in results:
                for hit in hits_in_batch:
                    entity = {
                        "id": hit.id,
                        "score": hit.score,
                        "distance": hit.distance,
                    }
                    # Add output fields
                    for field in output_fields:
                        if field in hit.entity.fields:
                            entity[field] = hit.entity.get(field)
                    
                    # Parse meta_json if present
                    if "meta_json" in entity and entity["meta_json"]:
                        try:
                            entity["metadata"] = json.loads(entity["meta_json"])
                        except json.JSONDecodeError:
                            entity["metadata"] = {}
                    else:
                        entity["metadata"] = {}
                        
                    hits.append(entity)
            return hits

        except Exception as e:
            logger.exception(f"Zilliz search failed: {e}")
            return []

    def insert(self, entities: List[Dict[str, Any]]) -> bool:
        """
        Insert entities into the collection.
        Each entity should match the collection schema fields.
        """
        if not self._connected:
            if not self.connect():
                return False

        try:
            # PyMilvus insert expects a list of dicts or a specific format
            # Since we have auto_id=True, we shouldn't include 'id' in the entities if we want Milvus to generate it.
            # However, our schema has auto_id=True, so we remove 'id' from entities if present.
            insert_data = []
            for e in entities:
                clean_e = {k: v for k, v in e.items() if k != 'id'}
                insert_data.append(clean_e)

            self._collection.insert(insert_data)
            self._collection.flush()
            logger.info(f"Inserted {len(insert_data)} entities into Zilliz.")
            return True
        except Exception as e:
            logger.exception(f"Zilliz insert failed: {e}")
            return False

    def close(self):
        """Disconnect from Zilliz."""
        try:
            connections.disconnect("default")
            self._connected = False
            self._collection = None
        except Exception:
            pass

# Global instance
zilliz = ZillizClient()
