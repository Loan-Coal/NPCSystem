"""
neo4j_queries.py - Cypher query strings for idempotency record persistence.

Does NOT: execute queries or hold connection state.

Dependencies injected: None.
"""

CYPHER_ENSURE_IDEMPOTENCY_CONSTRAINT = """
CREATE CONSTRAINT idempotency_record_key IF NOT EXISTS
FOR (r:IdempotencyRecord)
REQUIRE (r.idempotency_key, r.resource_scope) IS UNIQUE
"""

CYPHER_GET_RECORD = """
MATCH (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
RETURN r
LIMIT 1
"""

CYPHER_UPSERT_PENDING = """
MERGE (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
SET r.request_hash = $request_hash,
    r.status = 'pending',
    r.response_status_code = null,
    r.response_body = null,
    r.response_hash = null,
    r.created_at = datetime($created_at),
    r.expires_at = datetime($expires_at),
    r.pending_timeout_seconds = $pending_timeout_seconds,
    r.updated_at = datetime($created_at)
RETURN r
"""

CYPHER_CREATE_PENDING_IF_ABSENT = """
MERGE (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
ON CREATE SET r.request_hash = $request_hash,
              r.status = 'pending',
              r.response_status_code = null,
              r.response_body = null,
              r.response_hash = null,
              r.created_at = datetime($created_at),
              r.expires_at = datetime($expires_at),
              r.pending_timeout_seconds = $pending_timeout_seconds,
              r.updated_at = datetime($created_at),
              r._just_created = true
WITH r, coalesce(r._just_created, false) AS created
REMOVE r._just_created
RETURN created
"""

CYPHER_MARK_COMPLETE = """
MATCH (r:IdempotencyRecord {idempotency_key: $idempotency_key, resource_scope: $resource_scope})
WHERE r.request_hash = $request_hash
SET r.status = $status,
    r.response_status_code = $status_code,
    r.response_body = $response_body,
    r.response_hash = $response_hash,
    r.updated_at = datetime($updated_at)
RETURN count(r) AS updated_count
"""

CYPHER_DELETE_EXPIRED = """
MATCH (r:IdempotencyRecord)
WHERE r.expires_at < datetime($now_iso)
WITH collect(r) AS records, count(r) AS deleted_count
FOREACH (record IN records | DETACH DELETE record)
RETURN deleted_count
"""
