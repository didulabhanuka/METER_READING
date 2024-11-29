import sqlite3
import hashlib
import base64
import secrets
import time
import logging
import json
from authlib.oauth2.rfc6749 import OAuth2Error, AuthorizationServer
from authlib.oauth2.rfc6749.grants import ClientCredentialsGrant

DB_FILE = "apps/apiserver/auth.db"

# Initialize the database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT UNIQUE NOT NULL,
        client_secret TEXT NOT NULL,
        grant_type TEXT DEFAULT 'client_credentials',
        scope TEXT DEFAULT 'read',
        permissions TEXT DEFAULT '{}'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id TEXT NOT NULL,
        access_token TEXT NOT NULL,
        refresh_token TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        scope TEXT DEFAULT 'read',
        usage_count INTEGER DEFAULT 5
    )
    ''')

    conn.commit()
    conn.close()

class Client:
    def __init__(self, client_id, client_secret, grant_type, scope, permissions):
        self.client_id = client_id
        self.client_secret = client_secret
        self.grant_type = grant_type
        self.scope = scope
        self.permissions = permissions

    def check_grant_type(self, grant_type):
        return self.grant_type == grant_type

def load_clients_from_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT client_id, client_secret, grant_type, scope, permissions FROM clients")
    clients = [
        {
            "client_id": row[0],
            "client_secret": row[1],
            "grant_type": row[2],
            "scope": row[3],
            "permissions": json.loads(row[4])  # Parse JSON string to Python dict
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return clients

def save_client_to_db(client_data):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO clients (client_id, client_secret, grant_type, scope, permissions) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                client_data["client_id"],
                client_data["client_secret"],
                client_data.get("grant_type", "client_credentials"),
                client_data.get("scope", "read"),
                json.dumps(client_data.get("permissions", {})),  # Store permissions as JSON
            ),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError as e:
        logging.error(f"Failed to save client: {e}")

def load_tokens_from_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT client_id, access_token, refresh_token, expires_at, scope, usage_count FROM tokens")
    tokens = {}
    for row in cursor.fetchall():
        if row[0] not in tokens:
            tokens[row[0]] = []
        tokens[row[0]].append({
            "client_id": row[0],
            "access_token": row[1],
            "refresh_token": row[2],
            "expires_at": row[3],
            "scope": row[4],
            "usage_count": row[5],
        })
    conn.close()
    return tokens

class MyAuthorizationServer(AuthorizationServer):
    def handle_new_token(self, client, grant_type):
        try:
            # Generate a new token
            access_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            refresh_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            expires_in = 3600
            expires_at = int(time.time()) + expires_in

            token_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "expires_at": expires_at,
                "refresh_token": refresh_token,
                "scope": client.scope
            }

            # Save token to the database
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tokens (client_id, access_token, refresh_token, expires_at, scope, usage_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    hashlib.sha256(access_token.encode('utf-8')).hexdigest(),
                    hashlib.sha256(refresh_token.encode('utf-8')).hexdigest(),
                    expires_at,
                    client.scope,
                    5,  # Default usage count
                ),
            )
            conn.commit()
            conn.close()

            return token_data
        except Exception as e:
            logging.error(f"Error handling new token: {e}")
            raise OAuth2Error(error="token_generation_failed", description="Failed to generate token.")

    def authenticate_client(self, request, grant_type):
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')
        if grant_type == 'client_credentials':
            clients = load_clients_from_db()
            client_data = next((client for client in clients if client['client_id'] == client_id), None)
            if client_data and client_data['client_secret'] == client_secret:
                return Client(client_id, client_secret, client_data.get('grant_type', 'client_credentials'), client_data.get('scope', 'read'), client_data['permissions'])
        raise OAuth2Error(error='invalid_client', description='Client authentication failed.')

    def validate_token(self, token, token_type='access'):
        tokens = load_tokens_from_db()
        hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
        for client_id, token_entries in tokens.items():
            for entry in token_entries:
                if entry[f'{token_type}_token'] == hashed_token and time.time() < entry['expires_at']:
                    return entry
        return None

authorization_server = MyAuthorizationServer()
authorization_server.register_grant(ClientCredentialsGrant)
