import sqlite3
from contextlib import contextmanager
from flask import session, has_request_context
import config
import system_db


def _active_db_path():
    """Resolve the DB for the current request.

    Thread-safe: the path is read from the per-request session, never a
    shared global, so concurrent requests for different orgs cannot clobber
    each other.
    """
    if has_request_context() and session.get("org_id"):
        return system_db.get_org_db_path(session["org_id"])
    return config.SYSTEM_DB_PATH


@contextmanager
def get_db():
    path = _active_db_path()
    if path == config.SYSTEM_DB_PATH:
        # Route through the single shared, lock-guarded system connection so
        # we never open a second connection to the same file.
        with system_db.system_conn() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
    else:
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


@contextmanager
def get_db_cursor():
    with get_db() as conn:
        yield conn.cursor()


def execute(query, params=None):
    with get_db() as conn:
        cur = conn.execute(query, params or [])
        return cur.lastrowid


def fetchone(query, params=None):
    with get_db() as conn:
        cur = conn.execute(query, params or [])
        return cur.fetchone()


def fetchall(query, params=None):
    with get_db() as conn:
        cur = conn.execute(query, params or [])
        return cur.fetchall()


def executemany(query, params_list):
    with get_db() as conn:
        conn.executemany(query, params_list)
