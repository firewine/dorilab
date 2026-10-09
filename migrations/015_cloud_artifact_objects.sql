-- Optional durable bytes for the small free-hosting deployment. Existing
-- artifact/report metadata and authorization remain unchanged.
CREATE TABLE IF NOT EXISTS cloud_artifact_objects (
    namespace text NOT NULL CHECK (namespace IN ('artifacts','exports')),
    object_key text NOT NULL,
    content bytea NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0 AND byte_size <= 20971520),
    sha256 text NOT NULL CHECK (length(sha256)=64),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(namespace,object_key),
    CHECK (octet_length(content)=byte_size)
);
