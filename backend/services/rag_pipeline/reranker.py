"""
BGE Reranker v2-m3: rerank top-60 chunks to top-10 by cross-encoder relevance.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

_reranker_model = None


def _get_reranker():
    global _reranker_model
    if _reranker_model is None:
        try:
            from FlagEmbedding import FlagReranker
            logger.info("Loading bge-reranker-v2-m3…")
            _reranker_model = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
        except Exception as exc:
            logger.warning("bge-reranker-v2-m3 unavailable (%s). Using passthrough.", exc)
            _reranker_model = None
    return _reranker_model


class Reranker:
    def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Rerank up to 60 chunks against the query.
        Falls back to original RRF ordering if the model is unavailable.
        """
        if not chunks:
            return []

        reranker = _get_reranker()
        if reranker is None:
            return chunks[:top_k]

        try:
            pairs = [(query, c["content"]) for c in chunks]
            scores = reranker.compute_score(pairs, normalize=True)

            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)

            reranked = sorted(chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True)
            return reranked[:top_k]
        except Exception as exc:
            logger.warning("Reranking failed (%s). Using original order.", exc)
            return chunks[:top_k]
