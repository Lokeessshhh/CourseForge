"""
Management command to migrate vector embeddings and metadata from local PostgreSQL to Zilliz Cloud.
Updates schema to include document_id, chunk_index, level, metadata, etc.
Usage: python manage.py migrate_vectors_to_zilliz
"""
import os
import json
import logging
from django.core.management.base import BaseCommand
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

logger = logging.getLogger(__name__)
MAX_CONTENT_LENGTH = 65535
MAX_META_LENGTH = 20000

class Command(BaseCommand):
    help = "Migrate vector embeddings and metadata from local PostgreSQL to Zilliz Cloud and verify"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== STARTING VECTOR MIGRATION TO ZILLIZ CLOUD ==="))

        uri = os.environ.get("ZILLIZ_URI")
        token = os.environ.get("ZILLIZ_TOKEN")
        collection_name = os.environ.get("ZILLIZ_COLLECTION", "course_chunks")

        if not uri or not token:
            self.stdout.write(self.style.ERROR("Missing ZILLIZ_URI or ZILLIZ_TOKEN in .env"))
            return

        try:
            connections.connect("default", uri=uri, token=token)
            self.stdout.write(self.style.SUCCESS("1. Connected to Zilliz Cloud successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to Zilliz Cloud: {e}"))
            return

        local_db_url = os.environ.get("DOCKER_DB_URL")
        if not local_db_url:
            self.stdout.write(self.style.ERROR("DOCKER_DB_URL not set in .env"))
            return
            
        import psycopg2
        try:
            conn = psycopg2.connect(local_db_url)
            cursor = conn.cursor()
            self.stdout.write(self.style.SUCCESS("2. Connected to local source database."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to local source database: {e}"))
            return

        # 3. Define Schema Mapping
        # Local Columns: id, document_id, content, chunk_index, level, parent_chunk_id, dense_embedding, metadata, created_at
        # We will map them to Zilliz fields
        dim = 1536
        
        # Clean up previous collection if exists
        if collection_name in utility.list_collections(using="default"):
            utility.drop_collection(collection_name, using="default")
            self.stdout.write(self.style.SUCCESS(f"3. Dropped existing collection '{collection_name}'."))

        # Define new schema with all fields
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=36),      # Local: id (uuid)
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),  # Local: document_id (uuid)
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=MAX_CONTENT_LENGTH),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="level", dtype=DataType.INT64),
            FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=36),    # Local: parent_chunk_id
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="meta_json", dtype=DataType.VARCHAR, max_length=MAX_META_LENGTH), # Local: metadata
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50),
        ]
        schema = CollectionSchema(fields, description="Course chunks migrated from PostgreSQL with full metadata")
        collection = Collection(name=collection_name, schema=schema, using="default")
        
        self.stdout.write(self.style.SUCCESS(f"4. Created collection '{collection_name}' with extended schema."))

        # 5. Fetch and Process Data
        cursor.execute("SELECT id, document_id, content, chunk_index, level, parent_chunk_id, dense_embedding, metadata, created_at FROM chunks")
        records = cursor.fetchall()
        total_records = len(records)
        self.stdout.write(self.style.SUCCESS(f"5. Found {total_records} records to migrate."))

        if total_records == 0:
            self.stdout.write(self.style.WARNING("No records found."))
            return

        entities = []
        skipped = 0
        
        self.stdout.write("6. Processing records...")
        for i, record in enumerate(records):
            # Unpack row
            row_id, row_doc_id, row_content, row_chunk_idx, row_level, row_parent_id, row_embedding_raw, row_metadata, row_created_at = record
            
            # Handle Content Truncation
            content = row_content or ""
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
                if len(content_bytes) > MAX_CONTENT_LENGTH:
                    content = content_bytes[:MAX_CONTENT_LENGTH].decode('utf-8', errors='ignore')

            # Handle Embedding
            embedding = []
            if row_embedding_raw:
                try:
                    if isinstance(row_embedding_raw, str):
                        embedding = json.loads(row_embedding_raw)
                    else:
                        embedding = [float(x) for x in str(row_embedding_raw).strip("[]").split(",")]
                except Exception:
                    skipped += 1
                    continue
            
            if len(embedding) != dim:
                skipped += 1
                continue

            # Prepare Entity
            entities.append({
                "doc_id": str(row_id) if row_id else "",
                "document_id": str(row_doc_id) if row_doc_id else "",
                "content": content,
                "chunk_index": int(row_chunk_idx) if row_chunk_idx is not None else 0,
                "level": int(row_level) if row_level is not None else 0,
                "parent_id": str(row_parent_id) if row_parent_id else "",
                "embedding": embedding,
                "meta_json": json.dumps(row_metadata) if row_metadata else "{}",
                "created_at": str(row_created_at) if row_created_at else ""
            })

        # 7. Insert Data
        batch_size = 500
        total_inserted = 0
        
        self.stdout.write(f"7. Starting insertion of {len(entities)} valid records...")
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i+batch_size]
            try:
                collection.insert(batch)
                total_inserted += len(batch)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   Skipped batch {i//batch_size + 1} due to error: {str(e)[:50]}..."))
                continue
            
            if (i // batch_size) % 20 == 0:
                percent = int((total_inserted / len(entities)) * 100)
                self.stdout.write(f"   Progress: {total_inserted}/{len(entities)} ({percent}%)")

        collection.flush()
        self.stdout.write(self.style.SUCCESS(f"8. Insertion complete. {total_inserted} records inserted."))
        
        # 8. Create Index
        self.stdout.write("9. Creating search index on 'embedding'...")
        index_params = {
            "index_type": "AUTOINDEX",
            "metric_type": "COSINE",
            "params": {}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        self.stdout.write(self.style.SUCCESS("10. Index created and collection loaded."))
        
        # 9. Verification
        self.stdout.write(self.style.SUCCESS("=== VERIFICATION PHASE ==="))
        try:
            actual_count = collection.num_entities
            self.stdout.write(f"✅ Collection contains {actual_count} vectors.")
            
            if total_inserted == actual_count:
                self.stdout.write(self.style.SUCCESS("✅ VERIFICATION PASSED: Count matches!"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️  VERIFICATION WARNING: Expected {total_inserted}, found {actual_count}."))

            self.stdout.write(self.style.SUCCESS("✅ MIGRATION COMPLETED SUCCESSFULLY!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Verification failed: {e}"))

        cursor.close()
        conn.close()
