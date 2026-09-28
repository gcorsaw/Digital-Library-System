#!/usr/bin/env python3
import csv
import json
import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Ensure environment arrays synchronize locally
load_dotenv()

CSV_FILE = Path(__file__).with_name("test_data.csv")

def get_env(env_name, default=None):
    val = os.environ.get(env_name, default)
    if val is not None:
        val = val.strip()
    if not val:
        if env_name == "DB_PORT":
            return "5440"
        raise RuntimeError(f"Missing environment property configuration: {env_name}")
    return val

def parse_csv_to_jsonb_payload(file_path: Path) -> str:
    """Parses raw text rows into nested maps for relational constraints."""
    catalog_payload = []
    
    if not file_path.exists():
        print(f"[-] Error: Target data registry file '{file_path.name}' not found.")
        sys.exit(1)
        
    with open(file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Enforce database unique constraint structures
            isbn = row.get("isbn", "").strip() or None
            internal_code = row.get("internal_code", "").strip() or None
            
            if not isbn and not internal_code:
                continue  # Skip rows violating CHECK constraint
                
            # Process sub-relational parameters
            authors_list = []
            raw_authors = row.get("authors", "")
            if raw_authors:
                # Format: "Scott;Snyder;Writer|Greg;Capullo;Penciler"
                for entry in raw_authors.split("|"):
                    parts = [p.strip() for p in entry.split(";")]
                    if len(parts) >= 2:
                        first = parts[0]
                        last = parts[1]
                        role = parts[2] if len(parts) == 3 else "Author"
                        authors_list.append({"first_name": first, "last_name": last, "role": role})

            genres_list = [g.strip() for g in row.get("genres", "").split("|") if g.strip()]
            media_list = [m.strip() for m in row.get("media_types", "").split("|") if m.strip()]

            book_map = {
                "isbn": isbn,
                "internal_code": internal_code,
                "title": row.get("title", "").strip(),
                "publish_date": row.get("publish_date", "").strip() or None,
                "publisher": row.get("publisher", "").strip() or None,
                "language": row.get("language", "en").strip() or "en",
                "authors": authors_list,
                "genres": genres_list,
                "media_types": media_list
            }
            catalog_payload.append(book_map)
            
    return json.dumps(catalog_payload)

def trigger_database_bulk_ingest():
    print("[*] Parsing CSV records into structured JSON array mapping...")
    json_payload = parse_csv_to_jsonb_payload(CSV_FILE)
    
    print("[*] Connecting to local PostgreSQL cluster instance...")
    try:
        conn = psycopg2.connect(
            dbname=get_env("DB_NAME"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
            host=get_env("DB_HOST", "localhost"),
            port=int(get_env("DB_PORT"))
        )
        conn.autocommit = True
        
        with conn.cursor() as cur:
            print("[*] Invoking PL/pgSQL bulk_insert_books() engine...")
            cur.execute("SELECT * FROM bulk_insert_books(%s::jsonb);", (json_payload,))
            results = cur.fetchall()
            
            print(f"\n[+] SUCCESS: Ingested {len(results)} shared catalog assets!")
            for idx, row in enumerate(results, 1):
                print(f"   {idx}. ID: {row[0]} | Title: '{row[1]}'")
                
        conn.close()
    except Exception as err:
        print(f"\n[-] Ingestion critical crash event raised: {err}")
        sys.exit(1)

if __name__ == "__main__":
    trigger_database_bulk_ingest()