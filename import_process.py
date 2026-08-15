import sqlite3
import json
import os
from import_utils import mark_item_processed, get_import_items

DB_PATH = "inventory.db"

def process_customers(import_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    items = get_import_items(import_id)
    
    success = 0
    failure = 0
    
    for item_id, row_json in items:
        try:
            row = json.loads(row_json)
            name = row['name']
            phone = row.get('phone')
            credit = float(row.get('credit', 0))
            
            cursor.execute(
                """INSERT INTO customers (name, phone, credit)
                VALUES (?, ?, ?)""",
                (name, phone, credit)
            )
            mark_item_processed(item_id)
            success += 1
        except Exception as e:
            print(f"Error processing customer item {item_id}: {str(e)}")
            failure += 1
    
    conn.commit()
    conn.close()
    return success, failure

def process_products(import_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    items = get_import_items(import_id)
    
    success = 0
    failure = 0
    
    for item_id, row_json in items:
        try:
            row = json.loads(row_json)
            name = row['name']
            category = row['category']
            quantity = int(row['quantity'])
            price = float(row.get('price', 0))
            brand = row.get('brand')
            
            cursor.execute(
                """INSERT INTO items (name, category, quantity, price)
                VALUES (?, ?, ?, ?)""",
                (name, category, quantity, price)
            )
            mark_item_processed(item_id)
            success += 1
        except Exception as e:
            print(f"Error processing product item {item_id}: {str(e)}")
            failure += 1
    
    conn.commit()
    conn.close()
    return success, failure

