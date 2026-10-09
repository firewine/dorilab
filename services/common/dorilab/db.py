from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import database_url


@contextmanager
def connection():
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def one(query: str, params=()):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def all_rows(query: str, params=()):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
