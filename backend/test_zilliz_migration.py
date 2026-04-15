import os
import sys
from pymilvus import connections, Collection, utility
from random import random

def main():
    uri = os.environ.get("ZILLIZ_URI")
    token = os.environ.get("ZILLIZ_TOKEN")
    collection_name = "course_chunks"

    print("=== ZILLIZ MIGRATION VERIFICATION TEST ===")
    print(f"Target: {collection_name} at {uri[:30]}...")
    
    try:
        connections.connect("default", uri=uri, token=token)
        print("✅ 1. Connected to Zilliz Cloud successfully.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    if collection_name not in utility.list_collections():
        print(f"❌ Collection '{collection_name}' not found.")
        return

    collection = Collection(name=collection_name)
    collection.load()

    # 1. Check Count
    count = collection.num_entities
    print(f"\n📊 2. Statistics Check:")
    print(f"   - Total Entities: {count}")
    if count == 69509:
        print("   - ✅ Count matches expected 69,509.")
    else:
        print(f"   - ⚠️ Count mismatch! Expected 69,509.")

    # 2. Check Schema Fields
    schema_fields = [f.name for f in collection.schema.fields]
    expected_fields = ["id", "doc_id", "document_id", "content", "chunk_index", "level", "parent_id", "embedding", "meta_json", "created_at"]
    print(f"\n🔍 3. Schema Check:")
    print(f"   - Fields found: {schema_fields}")
    
    missing = [f for f in expected_fields if f not in schema_fields]
    if not missing:
        print("   - ✅ All 10 expected fields are present.")
    else:
        print(f"   - ❌ Missing fields: {missing}")

    # 3. Sample Data Check
    print(f"\n📝 4. Data Integrity Check (Fetching ID >= 1):")
    try:
        # Query for first few entities to verify schema fields are populated
        res = collection.query(expr="id >= 1", limit=1, output_fields=["doc_id", "content", "chunk_index", "level", "meta_json"])
        if res:
            sample = res[0]
            print(f"   - ID: {sample.get('id')}")
            print(f"   - Doc ID: {sample.get('doc_id')}")
            print(f"   - Chunk Index: {sample.get('chunk_index')}")
            print(f"   - Level: {sample.get('level')}")
            print(f"   - Content Preview: {str(sample.get('content'))[:60]}...")
            print(f"   - Metadata (JSON): {str(sample.get('meta_json'))[:50]}...")
            print("   - ✅ Sample data retrieval successful. All fields populated.")
        else:
            print("   - ⚠️ No data found with ID >= 1.")
    except Exception as e:
        print(f"   - ❌ Sample query failed: {e}")

    # 4. Search Test (Sanity Check)
    print(f"\n🔎 5. Vector Search Sanity Check:")
    try:
        # Create a random vector of dimension 1536
        search_vector = [[random() for _ in range(1536)]]
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        
        results = collection.search(
            data=search_vector,
            anns_field="embedding",
            param=search_params,
            limit=3,
            output_fields=["content", "chunk_index"]
        )
        
        print(f"   - ✅ Search returned {len(results[0])} results.")
        for i, hit in enumerate(results[0]):
            print(f"     Result {i+1}: Score={hit.score:.4f}, Content='{str(hit.entity.get('content'))[:40]}...'")
            
    except Exception as e:
        print(f"   - ❌ Search test failed: {e}")

    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    main()
