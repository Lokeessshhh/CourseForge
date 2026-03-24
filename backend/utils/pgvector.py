"""
pgvector utility functions for vector operations.
Provides helper functions for embedding storage and similarity search.
"""
import logging
from typing import List, Optional, Tuple, Any
import math

from django.db import connection

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Similarity score (0-1)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def euclidean_distance(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate Euclidean distance between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Distance value
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return float('inf')
    
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))


def vector_to_string(vec: List[float]) -> str:
    """
    Convert vector to PostgreSQL array string format.
    
    Args:
        vec: Vector as list of floats
        
    Returns:
        String representation for pgvector
    """
    return "[" + ",".join(str(v) for v in vec) + "]"


def string_to_vector(vec_str: str) -> List[float]:
    """
    Convert PostgreSQL vector string to list of floats.
    
    Args:
        vec_str: String like "[1.0,2.0,3.0]"
        
    Returns:
        List of floats
    """
    vec_str = vec_str.strip("[]()")
    if not vec_str:
        return []
    
    return [float(v.strip()) for v in vec_str.split(",")]


def find_similar_vectors(
    query_vec: List[float],
    table: str,
    vector_column: str = "embedding",
    top_k: int = 10,
    filter_conditions: Optional[str] = None,
    filter_params: Optional[List[Any]] = None,
) -> List[Tuple[Any, float]]:
    """
    Find similar vectors using pgvector cosine similarity.
    
    Args:
        query_vec: Query vector
        table: Table name
        vector_column: Name of the vector column
        top_k: Number of results
        filter_conditions: Optional WHERE clause conditions
        filter_params: Parameters for filter conditions
        
    Returns:
        List of (row_id, similarity) tuples
    """
    vec_str = vector_to_string(query_vec)
    
    where_clause = ""
    params = []
    if filter_conditions:
        where_clause = f"WHERE {filter_conditions}"
        params = filter_params or []
    
    sql = f"""
    SELECT id, 1 - ({vector_column} <=> %s::vector) as similarity
    FROM {table}
    {where_clause}
    ORDER BY {vector_column} <=> %s::vector
    LIMIT %s
    """
    
    params = params + [vec_str, vec_str, top_k]
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [(row[0], float(row[1])) for row in cursor.fetchall()]
    except Exception as e:
        logger.exception("Vector similarity search failed: %s", e)
        return []


def batch_insert_vectors(
    table: str,
    records: List[dict],
    vector_column: str = "embedding",
) -> int:
    """
    Batch insert records with vectors.
    
    Args:
        table: Table name
        records: List of dicts with 'id', 'vector', and other columns
        vector_column: Name of the vector column
        
    Returns:
        Number of records inserted
    """
    if not records:
        return 0
    
    # Build columns from first record
    columns = list(records[0].keys())
    if "vector" in columns:
        columns.remove("vector")
        columns.append(vector_column)
    
    values_sql = []
    params = []
    
    for record in records:
        placeholders = []
        for col in columns:
            if col == vector_column:
                placeholders.append("%s::vector")
                params.append(vector_to_string(record["vector"]))
            else:
                placeholders.append("%s")
                params.append(record.get(col))
        values_sql.append(f"({', '.join(placeholders)})")
    
    sql = f"""
    INSERT INTO {table} ({', '.join(columns)})
    VALUES {', '.join(values_sql)}
    """
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount
    except Exception as e:
        logger.exception("Batch vector insert failed: %s", e)
        return 0


def create_vector_index(
    table: str,
    column: str = "embedding",
    index_type: str = "ivfflat",
    lists: int = 100,
    metric: str = "cosine",
) -> bool:
    """
    Create a vector index on a column.
    
    Args:
        table: Table name
        column: Vector column name
        index_type: Index type (ivfflat, hnsw)
        lists: Number of lists for IVFFlat
        metric: Distance metric (cosine, l2, ip)
        
    Returns:
        True if successful
    """
    index_name = f"idx_{table}_{column}_{index_type}"
    
    if index_type == "ivfflat":
        sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table}
        USING ivfflat ({column} vector_cosine_ops)
        WITH (lists = {lists})
        """
    elif index_type == "hnsw":
        sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table}
        USING hnsw ({column} vector_cosine_ops)
        """
    else:
        logger.error("Unknown index type: %s", index_type)
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        return True
    except Exception as e:
        logger.exception("Vector index creation failed: %s", e)
        return False


def get_vector_stats(table: str, column: str = "embedding") -> dict:
    """
    Get statistics about vectors in a table.
    
    Args:
        table: Table name
        column: Vector column name
        
    Returns:
        Stats dict with count, dimensions, etc.
    """
    sql = f"""
    SELECT 
        COUNT(*) as total,
        COUNT({column}) as with_embedding,
        array_length({column}, 1) as dimensions
    FROM {table}
    """
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
            
            return {
                "total_records": row[0],
                "records_with_embedding": row[1],
                "dimensions": row[2],
            }
    except Exception as e:
        logger.exception("Vector stats query failed: %s", e)
        return {}


def normalize_vector(vec: List[float]) -> List[float]:
    """
    Normalize a vector to unit length.
    
    Args:
        vec: Input vector
        
    Returns:
        Normalized vector
    """
    if not vec:
        return vec
    
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    
    return [v / norm for v in vec]


def mean_vector(vectors: List[List[float]]) -> List[float]:
    """
    Calculate mean vector from a list of vectors.
    
    Args:
        vectors: List of vectors
        
    Returns:
        Mean vector
    """
    if not vectors:
        return []
    
    n = len(vectors)
    dim = len(vectors[0])
    
    result = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            result[i] += vec[i]
    
    return [v / n for v in result]
