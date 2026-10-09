"""Prepare ONLY the previously verified Neon test branch for the CPU backend.

No seed, general migration, original DB switch, GPU access, or secret rotation.
Credentials and source bytes are read from protected mounts, never arguments.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import secrets
import tarfile

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from db_transfer import manifest, save

HOST='ep-empty-hall-b59hexb4.c-7.us-east-2.aws.neon.tech'
ROLE='dorilab_cloud_runtime'
QUOTA=64*1024*1024


def original_view(value):
    value=json.loads(json.dumps(value))
    value['tables'].pop('cloud_artifact_objects',None)
    value['tables'].pop('schema_migrations',None)
    for key in ('columns','constraints','indexes'):
        value[key]=[item for item in value[key] if item.get('table_name',item.get('tablename')) != 'cloud_artifact_objects']
    value.pop('server',None)
    return value


def main():
    records=Path('/records')
    target=Path('/credentials')
    result=records/'cloud-preparation.json'
    if result.exists():
        raise RuntimeError('already prepared; no schema, roles, or credentials changed')
    before_verified=json.loads((records/'neon_test-result.json').read_text())
    if not before_verified.get('passed'):
        raise RuntimeError('verified Neon test restore required')
    source=json.loads((records/'source-manifest.json').read_text())
    config=configparser.ConfigParser(interpolation=None)
    config.read(os.environ['PGSERVICEFILE'])
    fields=dict(config['neon_test'])
    if fields['host'] != HOST or fields['dbname'] != 'neondb' or fields['sslmode'] != 'verify-full':
        raise RuntimeError('unexpected database target')
    conn=psycopg.connect('service=neon_test',row_factory=dict_row)
    with conn:
        if conn.info.host != HOST or not conn.pgconn.ssl_in_use:
            raise RuntimeError('expected verified TLS endpoint')
        before=manifest(conn)
        if original_view(source) != original_view(before):
            raise RuntimeError('restored baseline changed; preparation refused')
        references=[]
        with conn.cursor() as cur:
            for table,namespace in [('artifact_versions','artifacts'),('report_exports','exports')]:
                cur.execute(sql.SQL('SELECT object_key,byte_size,sha256 FROM {} ORDER BY object_key').format(sql.Identifier(table)))
                references.extend(dict(row,namespace=namespace) for row in cur.fetchall())
        objects=[]
        with tarfile.open(records/'artifacts-exports.tar.gz','r:gz') as archive:
            for row in references:
                name=row['namespace']+'/'+row['object_key']
                member=archive.getmember(name)
                if not member.isfile() or member.size>20*1024*1024:
                    raise RuntimeError('unexpected artifact archive entry')
                data=archive.extractfile(member).read()
                if len(data)!=row['byte_size'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                    raise RuntimeError('artifact baseline mismatch')
                objects.append((row,data))
        if sum(len(data) for _,data in objects)>QUOTA:
            raise RuntimeError('initial artifact quota exceeded')
        runtime_path=target/'cloud-runtime-db.json'
        if runtime_path.exists():
            runtime=json.loads(runtime_path.read_text())
            if runtime.get('host')!=HOST or runtime.get('user')!=ROLE:
                raise RuntimeError('existing runtime credential is not for this deployment')
        else:
            runtime={key:fields[key] for key in ('host','dbname','sslmode','sslrootcert','channel_binding')}
            runtime.update(user=ROLE,password=secrets.token_hex(32))
            save(runtime_path,runtime)
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(ROLE,))
            if cur.fetchone():
                with psycopg.connect(**runtime,connect_timeout=15):
                    pass  # reuse matching credential; never rotate unknown role
            else:
                cur.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}')
                            .format(sql.Identifier(ROLE),sql.Literal(runtime['password'])))
            version='015_cloud_artifact_objects.sql'
            cur.execute('SELECT 1 FROM schema_migrations WHERE version=%s',(version,))
            if not cur.fetchone():
                cur.execute(Path('/app/migrations/'+version).read_text())
                cur.execute('INSERT INTO schema_migrations(version) VALUES (%s)',(version,))
            for row,data in objects:
                cur.execute('SELECT sha256,byte_size FROM cloud_artifact_objects WHERE namespace=%s AND object_key=%s',(row['namespace'],row['object_key']))
                previous=cur.fetchone()
                if previous and (previous['sha256']!=row['sha256'] or previous['byte_size']!=len(data)):
                    raise RuntimeError('existing durable object differs; refusing replacement')
                cur.execute('INSERT INTO cloud_artifact_objects(namespace,object_key,content,byte_size,sha256) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                            (row['namespace'],row['object_key'],data,len(data),row['sha256']))
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE neondb TO {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            for table in cur.fetchall():
                operations='SELECT' if table['tablename']=='schema_migrations' else 'SELECT,INSERT,UPDATE,DELETE'
                cur.execute(sql.SQL('GRANT '+operations+' ON TABLE public.{} TO {}').format(sql.Identifier(table['tablename']),sql.Identifier(ROLE)))
            cur.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(ROLE)))
        after=manifest(conn)
        if original_view(before)!=original_view(after):
            raise RuntimeError('original business rows changed; transaction rolled back')
    mapping=json.loads(Path('/source-secrets/sites_identities.json').read_text())
    mapping['backend_location']='SERVER'
    mapping_path=target/'cloud-sites-identities.json'
    if mapping_path.exists() and json.loads(mapping_path.read_text())!=mapping:
        raise RuntimeError('existing identity mapping differs; no overwrite')
    if not mapping_path.exists(): save(mapping_path,mapping)
    save(result,dict(passed=True,endpoint=HOST,scope='NEON_TEST_ONLY',business_tables_preserved=39,
                     durable_objects=len(objects),durable_bytes=sum(len(data) for _,data in objects),
                     runtime_role=ROLE,ddl_allowed=False,credentials_rotated=False,mode='DEMO'))
    print('CLOUD_TEST_DATABASE_PREPARED; original business rows and file hashes preserved')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # SQL errors can contain a credential literal: never print raw errors.
        print('CLOUD_PREPARATION_FAILED: '+type(error).__name__)
        raise SystemExit(1)
