"""Read-only snapshot/restore verification. Run using the existing CPU app image.

This tool never migrates, seeds, truncates, or starts a worker. Actual restore is
pg_restore --single-transaction into a separately verified empty test database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
import time
from uuid import UUID
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import psycopg
from psycopg import IsolationLevel
from psycopg import sql
from psycopg.rows import dict_row


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary.replace(path)


def prepare_neon(uri_path, destination, expected_host):
    source = Path(uri_path)
    if source.stat().st_mode & 0o077:
        raise ValueError("connection secret must have mode 600")
    value = urlsplit(source.read_text().strip())
    if (value.scheme not in ("postgres", "postgresql") or value.hostname != expected_host
            or not expected_host.endswith(".neon.tech") or "-pooler" in expected_host
            or value.port not in (None, 5432)):
        raise ValueError("expected an approved direct Neon endpoint")
    if not value.password or not value.username or value.fragment:
        raise ValueError("missing or malformed connection credentials")
    if set(parse_qs(value.query)) - {"sslmode", "channel_binding"}:
        raise ValueError("unexpected connection option")
    fields = {"host": expected_host, "port": "5432", "dbname": unquote(value.path[1:]),
              "user": unquote(value.username), "password": unquote(value.password),
              "sslmode": "verify-full", "sslrootcert": "/etc/ssl/certs/ca-certificates.crt",
              "channel_binding": "require", "connect_timeout": "20"}
    if any(not v or any(c in v for c in "\n\r\0") for v in fields.values()):
        raise ValueError("malformed connection field")
    target = Path(destination)
    content = "[neon_test]\n" + "".join(f"{k}={v}\n" for k, v in fields.items())
    if target.exists():
        if target.read_text() != content:
            raise ValueError("existing credential differs; refusing replacement")
        return
    with target.open("x", encoding="utf-8") as stream:
        os.chmod(target, 0o600)
        stream.write(content)


def connect(service):
    if service == "source":
        from dorilab.config import database_url
        return psycopg.connect(database_url(), row_factory=dict_row)
    if service == "local_test":
        return psycopg.connect(host=os.environ["TRANSFER_LOCAL_HOST"], dbname="restore_test",
                               user="restore_test", password=Path("/secrets/local-test.password").read_text().strip(),
                               connect_timeout=10, row_factory=dict_row)
    if service == "neon_test":
        conn = psycopg.connect("service=neon_test", row_factory=dict_row)
        if (conn.info.host != os.environ["TRANSFER_NEON_HOST"] or conn.info.dbname != "neondb"
                or conn.info.get_parameters().get("sslmode") != "verify-full" or not conn.pgconn.ssl_in_use):
            conn.close()
            raise ValueError("unapproved endpoint or certificate verification mode")
        return conn
    raise ValueError("unsupported database selection")


def manifest(conn):
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
        cur.execute("SET DateStyle='ISO, YMD'")
        cur.execute("SELECT current_database() AS database,current_setting('server_version') AS version")
        server = cur.fetchone()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables = {}
        for item in cur.fetchall():
            name = item["tablename"]
            cur.execute(sql.SQL("SELECT to_jsonb(t) AS value FROM public.{} t").format(sql.Identifier(name)))
            # Hash complete rows, not merely counts. Sorting hashes is independent
            # of locale, row order, UUID order, and JSON field order.
            hashes = sorted(digest(row["value"]) for row in cur.fetchall())
            tables[name] = {"rows": len(hashes), "sha256": digest(hashes)}
        cur.execute("""SELECT c.relname AS table_name,a.attname AS column_name,
                     format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null,
                     a.attgenerated AS generated,pg_get_expr(d.adbin,d.adrelid) AS default_expr
                     FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
                     LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
                     WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname,a.attnum""")
        columns = cur.fetchall()
        cur.execute("""SELECT c.relname AS table_name,con.conname,con.contype,con.convalidated,
                     pg_get_constraintdef(con.oid) AS definition FROM pg_constraint con
                     JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='public' AND con.contype<>'n' ORDER BY c.relname,con.conname""")
        # PostgreSQL 18 represents NOT NULL in pg_constraint as well. Column
        # attnotnull above verifies that same invariant on both server versions.
        constraints = cur.fetchall()
        cur.execute("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname")
        indexes = cur.fetchall()
        cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
        sequences = {}
        for sequence in cur.fetchall():
            name = sequence["sequencename"]
            cur.execute(sql.SQL("SELECT last_value,is_called FROM public.{}").format(sql.Identifier(name)))
            sequences[name] = cur.fetchone()
        searches = []
        if "retrieval_runs" in tables:
            cur.execute("SELECT id,project_id,query FROM retrieval_runs ORDER BY id")
            for run in cur.fetchall():
                # Exercise the same native simple-FTS rank primitive used by the
                # existing API, with project filtering; do not create a new receipt.
                cur.execute("""SELECT dc.id,dc.artifact_id,dc.ordinal,dc.text_sha256,
                             ts_rank_cd(dc.search_vector,q.value)::double precision AS score
                             FROM document_chunks dc CROSS JOIN
                             (SELECT websearch_to_tsquery('simple',%s) AS value) q
                             WHERE dc.project_id=%s AND dc.search_vector @@ q.value
                             ORDER BY score DESC,dc.artifact_id,dc.ordinal,dc.id""", (run["query"],run["project_id"]))
                results = [{k: str(v) if isinstance(v, UUID) else v
                            for k,v in row.items()} for row in cur.fetchall()]
                searches.append({"retrieval_id": str(run["id"]), "matches":len(results), "sha256":digest(results)})
        return {"server":server, "tables":tables, "columns":columns, "constraints":constraints,
                "indexes":indexes, "sequences":sequences, "searches":searches}


def differences(expected, actual):
    return [key for key in ("tables","columns","constraints","indexes","sequences","searches")
            if expected[key] != actual[key]]


def check_empty(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) AS count FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')""")
        if cur.fetchone()["count"]:
            raise ValueError("test database is not empty; restore refused, no data removed")


def check_files(conn, archive_path):
    references = []
    for table, prefix in (("artifact_versions", "artifacts"), ("report_exports", "exports")):
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT object_key,sha256,byte_size FROM public.{} ORDER BY object_key")
                        .format(sql.Identifier(table)))
            references.extend({"path":prefix+"/"+row["object_key"],"sha256":row["sha256"],
                               "bytes":row["byte_size"]} for row in cur.fetchall())
    failures = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for reference in references:
            try:
                stream = archive.extractfile(reference["path"])
                if stream is None:
                    raise ValueError("not a regular file")
                value = stream.read()
                if len(value) != reference["bytes"] or hashlib.sha256(value).hexdigest() != reference["sha256"]:
                    failures.append(reference["path"])
            except (KeyError,ValueError):
                failures.append(reference["path"])
    return {"passed":not failures,"checked_references":len(references),"failed_paths":failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command",choices=["snapshot","verify","empty","files","prepare-neon"])
    parser.add_argument("--database",choices=["source","local_test","neon_test"],default="source")
    parser.add_argument("--records",default="/records")
    parser.add_argument("--host")
    args = parser.parse_args()
    records = Path(args.records)
    if args.command == "prepare-neon":
        prepare_neon("/secrets/neon-test.url","/credentials/neon-test.pgservice.conf",args.host)
        print("NEON_SECRET_READY (certificate + hostname verification required)")
        return
    with connect(args.database) as conn:
        conn.isolation_level = IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        conn.execute("SET statement_timeout='60s'")
        if args.command == "empty":
            check_empty(conn)
            save(records/f"{args.database}-empty.json", {"empty":True,"tls":conn.pgconn.ssl_in_use,
                 "host":conn.info.host,"database":conn.info.dbname,"version":conn.info.server_version})
            print("EMPTY_TEST_DATABASE_CONFIRMED")
            return
        if args.command == "files":
            result = check_files(conn,records/"artifacts-exports.tar.gz")
            save(records/"file-backup-result.json",result)
            print(json.dumps(result))
            if not result["passed"]:
                raise SystemExit(1)
            return
        if args.command == "snapshot":
            snapshot = conn.execute("SELECT pg_export_snapshot() AS id").fetchone()["id"]
            if not re.fullmatch(r"[0-9A-F]+-[0-9A-F]+-[0-9]+",snapshot):
                raise ValueError("unexpected snapshot format")
            save(records/"source-manifest.json",manifest(conn))
            (records/"snapshot.id").write_text(snapshot+"\n")
            deadline = time.monotonic()+180
            while not (records/"snapshot.done").exists():
                if time.monotonic()>deadline:
                    raise ValueError("snapshot expired before backup completed")
                time.sleep(0.2)
            print("CONSISTENT_SNAPSHOT_BACKED_UP")
            return
        actual = manifest(conn)
        expected = json.loads((records/"source-manifest.json").read_text())
        mismatches = differences(expected,actual)
        save(records/f"{args.database}-manifest.json",actual)
        result = {"passed":not mismatches,"differences":mismatches,"table_count":len(actual["tables"]),
                  "counts":{k:v["rows"] for k,v in actual["tables"].items()},
                  "search_queries":len(actual["searches"]),"source_version":expected["server"]["version"],
                  "target_version":actual["server"]["version"],"tls":conn.pgconn.ssl_in_use}
        save(records/f"{args.database}-result.json",result)
        print(json.dumps(result,ensure_ascii=False))
        if mismatches:
            raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (psycopg.Error, ValueError, OSError) as error:
        # Libpq errors can include query text or connection information. Do not
        # emit the raw exception (backup contents are also non-public).
        if isinstance(error, ValueError) and str(error) == "test database is not empty; restore refused, no data removed":
            print("RESTORE_REFUSED_NONEMPTY: no data removed",flush=True)
        else:
            print(f"TRANSFER_FAILED: {type(error).__name__}",flush=True)
        raise SystemExit(1)
