"""
RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval) service.
Builds a tree of document summaries for multi-scale retrieval.
"""
import logging
from typing import List, Optional, Dict, Any
import uuid


logger = logging.getLogger(__name__)


class RaptorService:
    """
    Implements RAPTOR for hierarchical document summarization.
    
    Tree structure:
    - Level 0: Original chunks
    - Level 1: Summaries of clusters of Level 0 chunks
    - Level 2+: Higher-level abstractions
    """

    def __init__(
        self,
        max_levels: int = 3,
        cluster_size: int = 10,
        llm_client=None,
    ):
        """
        Initialize RAPTOR service.
        
        Args:
            max_levels: Maximum tree depth
            cluster_size: Number of chunks per cluster
            llm_client: LLM client for summarization
        """
        self.max_levels = max_levels
        self.cluster_size = cluster_size
        self.llm_client = llm_client

    def build_tree(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build RAPTOR tree for a document.
        
        Args:
            document_id: Document ID
            chunks: List of chunk dicts with content and embeddings
            
        Returns:
            Tree structure with nodes at each level
        """
        tree = {"document_id": document_id, "levels": {}}
        
        # Level 0: Original chunks
        tree["levels"][0] = {
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "content": chunk["content"],
                    "embedding": chunk.get("embedding"),
                    "source_chunks": [chunk.get("id")],
                    "level": 0,
                }
                for chunk in chunks
            ]
        }
        
        current_level = 0
        current_nodes = tree["levels"][0]["nodes"]
        
        # Build higher levels
        while current_level < self.max_levels - 1 and len(current_nodes) >= self.cluster_size:
            next_level = current_level + 1
            
            # Cluster nodes
            clusters = self._cluster_nodes(current_nodes)
            
            # Create summaries for each cluster
            summary_nodes = []
            for cluster in clusters:
                summary = self._summarize_cluster(cluster)
                if summary:
                    summary_nodes.append(summary)
            
            if not summary_nodes:
                break
                
            tree["levels"][next_level] = {"nodes": summary_nodes}
            current_level = next_level
            current_nodes = summary_nodes
        
        return tree

    def _cluster_nodes(
        self,
        nodes: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        """
        Cluster nodes based on embedding similarity.
        
        Args:
            nodes: List of node dicts
            
        Returns:
            List of clusters (each cluster is a list of nodes)
        """
        clusters = []
        
        # Simple greedy clustering based on similarity
        remaining = list(nodes)
        
        while remaining:
            # Start new cluster with first remaining node
            cluster = [remaining.pop(0)]
            
            # Find similar nodes to add to cluster
            i = 0
            while i < len(remaining) and len(cluster) < self.cluster_size:
                node = remaining[i]
                
                # Check similarity with cluster members
                if self._is_similar_to_cluster(node, cluster):
                    cluster.append(remaining.pop(i))
                else:
                    i += 1
            
            clusters.append(cluster)
        
        return clusters

    def _is_similar_to_cluster(
        self,
        node: Dict[str, Any],
        cluster: List[Dict[str, Any]],
        threshold: float = 0.7,
    ) -> bool:
        """Check if node is similar enough to join cluster."""
        if not node.get("embedding") or not cluster:
            return True  # Default to joining if no embeddings
        
        node_vec = node["embedding"]
        
        for cluster_node in cluster:
            if cluster_node.get("embedding"):
                similarity = self._cosine_similarity(
                    node_vec,
                    cluster_node["embedding"],
                )
                if similarity >= threshold:
                    return True
        
        return False

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

    def _summarize_cluster(
        self,
        cluster: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a summary node for a cluster.
        
        Args:
            cluster: List of nodes in the cluster
            
        Returns:
            Summary node dict or None if summarization fails
        """
        # Combine cluster content
        combined_content = "\n\n".join([
            node["content"] for node in cluster
        ])
        
        # Generate summary
        if self.llm_client:
            try:
                summary = self._llm_summarize(combined_content)
            except Exception as e:
                logger.warning("LLM summarization failed: %s", e)
                summary = self._extractive_summarize(cluster)
        else:
            summary = self._extractive_summarize(cluster)
        
        if not summary:
            return None
        
        # Get embeddings for summary
        from services.llm.embeddings import EmbeddingService
        embedder = EmbeddingService()
        embedding = embedder.embed_text(summary, model="fallback")
        
        return {
            "id": str(uuid.uuid4()),
            "content": summary,
            "embedding": embedding,
            "source_chunks": [n["id"] for n in cluster],
            "level": max(n.get("level", 0) for n in cluster) + 1,
        }

    def _llm_summarize(self, content: str) -> str:
        """Use LLM to generate summary."""
        prompt = f"""Summarize the following text concisely while preserving key information:

{content[:4000]}

Summary:"""

        response = self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        
        return response.get("content", "").strip()

    def _extractive_summarize(
        self,
        cluster: List[Dict[str, Any]],
        max_sentences: int = 3,
    ) -> str:
        """Create extractive summary from cluster."""
        # Simple approach: take first sentences from each node
        sentences = []
        
        for node in cluster:
            content = node["content"]
            # Split into sentences
            parts = content.replace("!", ".").replace("?", ".").split(".")
            for part in parts[:2]:  # Take first 2 sentences per node
                part = part.strip()
                if part and len(part) > 10:
                    sentences.append(part)
        
        # Take top sentences
        summary = ". ".join(sentences[:max_sentences])
        if summary and not summary.endswith("."):
            summary += "."
        
        return summary

    def retrieve(
        self,
        query_embedding: List[float],
        tree: Dict[str, Any],
        top_k: int = 10,
        level_weights: Optional[Dict[int, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve from RAPTOR tree at multiple levels.
        
        Args:
            query_embedding: Query vector
            tree: RAPTOR tree structure
            top_k: Number of results
            level_weights: Optional weights for each level
            
        Returns:
            List of relevant nodes from all levels
        """
        if level_weights is None:
            level_weights = {0: 1.0, 1: 0.8, 2: 0.6}
        
        all_results = []
        
        for level, data in tree.get("levels", {}).items():
            weight = level_weights.get(level, 0.5)
            
            for node in data.get("nodes", []):
                if not node.get("embedding"):
                    continue
                
                similarity = self._cosine_similarity(
                    query_embedding,
                    node["embedding"],
                )
                
                # Weight by level
                weighted_score = similarity * weight
                
                all_results.append({
                    "id": node["id"],
                    "content": node["content"],
                    "level": level,
                    "score": weighted_score,
                    "source_chunks": node.get("source_chunks", []),
                })
        
        # Sort by score and return top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]


def build_raptor_tree(
    document_id: str,
    chunks: List[Dict[str, Any]],
    llm_client=None,
) -> Dict[str, Any]:
    """
    Convenience function to build RAPTOR tree.
    
    Args:
        document_id: Document ID
        chunks: List of chunks
        llm_client: Optional LLM client
        
    Returns:
        RAPTOR tree structure
    """
    service = RaptorService(llm_client=llm_client)
    return service.build_tree(document_id, chunks)
