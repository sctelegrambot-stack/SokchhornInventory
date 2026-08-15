import csv
import json
import os
import sqlite3
from uuid import uuid4

DB_PATH = "inventory.db"
IMPORT_DIR = "imports"

os.makedirs(IMPORT_DIR, exist_ok=True)

def create_import(import_type, file_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO imports (type, file_path) VALUES (?, ?)",
        (import_type, file_path)
    )
    import_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return import_id

def create_import_item(import_id, row_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO import_items (import_id, row_data) VALUES (?, ?)",
        (import_id, row_data)
    )
    conn.commit()
    conn.close()

def get_import(import_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, file_path, status FROM imports WHERE id = ?",
        (import_id,)
    )
    import_data = cursor.fetchone()
    conn.close()
    return import_data

def get_import_items(import_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, row_data FROM import_items WHERE import_id = ? AND processed = 0",
        (import_id,)
    )
    items = cursor.fetchall()
    conn.close()
    return items

def update_import_status(import_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE imports SET status = ? WHERE id = ?",
        (status, import_id)
    )
    conn.commit()
    conn.close()

def mark_item_processed(item_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE import_items SET processed = 1 WHERE id = ?",
        (item_id,)
    )
    conn.commit()
    conn.close()
