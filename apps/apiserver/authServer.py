import sqlite3
import hashlib
import base64
import secrets
import time
import logging
import json
from authlib.oauth2.rfc6749 import OAuth2Error, AuthorizationServer
from authlib.oauth2.rfc6749.grants import ClientCredentialsGrant
import jwt
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from apps.config import Config
from flask import g
import os
import datetime

# Define the log directory and log file path
log_dir = os.path.join(os.getcwd(), 'Logs')
log_file = os.path.join(log_dir, 'auth_server.log')

# Constants
DB_FILE = "apps/apiserver/auth.db"
TOKEN_EXPIRATION_TIME = 3600  # 1 hour for access token
REFRESH_TOKEN_EXPIRATION_TIME = 3600  # 1 hour for refresh token
DEFAULT_USAGE_COUNT = 5
SECRET_KEY = Config.SECRET_KEY  # Store securely in environment variables
ALGORITHM = Config.HASH_ALGORITHM  # HMAC SHA-256 for signing JWTs

def execute_query(query, params=None, fetch=False, commit=False):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                if commit:
                    conn.commit()
                if fetch:
                    if query.strip().upper().startswith("SELECT"):
                        return cursor.fetchall()
                    else:
                        logging.warning("Fetch requested for a non-SELECT query.")
                        return None
            except sqlite3.DatabaseError as e:
                logging.error(f"Query execution error: {e}\nQuery: {query}\nParams: {params}")
                raise
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
        raise

def initialize_database():
    try:
        execute_query('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            client_secret TEXT NOT NULL,
            grant_type TEXT DEFAULT 'client_credentials',
            scope TEXT DEFAULT 'read',
            permissions TEXT DEFAULT '{}'
        )
        ''', commit=True)

        execute_query(f'''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            scope TEXT DEFAULT 'read',
            usage_count INTEGER DEFAULT {DEFAULT_USAGE_COUNT}
        )
        ''', commit=True)

    except sqlite3.DatabaseError as e:
        logging.error(f"Error initializing database schema: {e}")
        raise

class OAuth2Client:
    """Represents an OAuth2 client."""
    def __init__(self, client_id, client_secret, grant_type, scope, permissions):
        self.client_id = client_id
        self.client_secret = client_secret
        self.grant_type = grant_type
        self.scope = scope
        self.permissions = permissions

    def matches_grant_type(self, grant_type):
        """Check if the client's grant type matches the requested one."""
        return self.grant_type == grant_type

def retrieve_clients_from_db():
    """Fetch all client records from the database."""
    rows = execute_query("SELECT client_id, client_secret, grant_type, scope, permissions FROM clients", fetch=True)
    return [
        {
            "client_id": row[0],
            "client_secret": row[1],
            "grant_type": row[2],
            "scope": row[3],
            "permissions": row[4]  
        }
        for row in rows
    ]

def add_client_to_db(client_data):
    """Insert a new client record into the database."""
    try:
        execute_query("""
            INSERT INTO clients (client_id, client_secret, grant_type, scope, permissions) 
            VALUES (?, ?, ?, ?, ?)
        """, (
            client_data["client_id"],
            client_data["client_secret"],
            client_data.get("grant_type", "client_credentials"),
            client_data.get("scope", "read"),
            client_data.get("permissions", "none"), 
        ), commit=True)
    except sqlite3.IntegrityError as e:
        logging.error(f"Failed to save client: {e}")

def retrieve_tokens_from_db():
    """Fetch all token records from the database."""
    rows = execute_query("SELECT client_id, access_token, refresh_token, expires_at, scope, usage_count FROM tokens", fetch=True)
    tokens = {}
    for row in rows:
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
    return tokens

def get_token_from_db(access_token):
    rows = execute_query("""
        SELECT client_id, access_token, refresh_token, expires_at, scope, usage_count
        FROM tokens
        WHERE access_token = ?
        """, (access_token,), fetch=True)
    
    if not rows or len(rows) == 0:
        return None
    
    row = rows[0]
    if any(value is None for value in row):
        return None

    token = {
        "client_id": row[0],
        "access_token": row[1],
        "refresh_token": row[2],
        "expires_at": row[3],
        "scope": row[4],
        "usage_count": row[5],
    }
    return token

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 for secure storage."""
    salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=64,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode())).decode()

def is_token_expired(expires_at):
    current_time = datetime.datetime.utcnow()
    expiration_time = datetime.datetime.utcfromtimestamp(expires_at)
    return current_time > expiration_time

class OAuth2AuthorizationServer(AuthorizationServer):
   
    def generate_jwt_token(self, client, usage_count):
        """Generate and store a new access token as a JWT for the client."""
        payload = {
            "client_id": client.client_id,
            "scope": client.scope,
            "permissions": client.permissions,
            "exp": time.time() + TOKEN_EXPIRATION_TIME,  # Expiration time for access token
            "iat": time.time(),  # Issued at time
        }

        # Generate access token (JWT)
        access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        # Generate refresh token (Random string to be stored securely)
        refresh_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        refresh_token_expiry = int(time.time()) + REFRESH_TOKEN_EXPIRATION_TIME
        print(client.client_id)
        execute_query("""
            DELETE FROM tokens WHERE client_id = ?
        """, (client.client_id,), commit=True)

        execute_query("""
            INSERT INTO tokens (client_id, access_token, refresh_token, expires_at, scope, usage_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            client.client_id,
            access_token,
            hashlib.sha256(refresh_token.encode('utf-8')).hexdigest(),
            int(time.time()) + TOKEN_EXPIRATION_TIME,
            client.scope,
            usage_count
        ), commit=True)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": TOKEN_EXPIRATION_TIME,
            "expires_at": int(time.time()) + TOKEN_EXPIRATION_TIME,
            "refresh_token": refresh_token,
            "scope": client.scope
        }

    def refresh_access_token(self, refresh_token):
        """Generate a new access token using a refresh token."""
        tokens = retrieve_tokens_from_db()
        hashed_refresh_token = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

        for client_id, token_entries in tokens.items():
            for entry in token_entries:
                if entry['usage_count'] <= 0:
                    raise OAuth2Error(error="invalid_grant", description="Refresh token is expired.")
                if entry['refresh_token'] == hashed_refresh_token and time.time() < entry['expires_at'] and entry['usage_count']>0:
                    # If the refresh token is valid, issue a new access token
                    client_data = next(client for client in retrieve_clients_from_db() if client['client_id'] == client_id)
                    new_access_token = self.generate_jwt_token(OAuth2Client(
                        client_id=client_id,
                        client_secret="dummy",
                        grant_type=client_data.get('grant_type', 'client_credentials'),
                        scope=client_data.get('scope', 'read'),
                        permissions=client_data.get('permissions')
                    ), entry['usage_count'] - 1 )
                    return new_access_token

        raise OAuth2Error(error="invalid_grant", description="Refresh token is invalid or expired.")

    def authenticate_client(self, request, grant_type):
        """Authenticate a client using their client_id and client_secret."""
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')

        if grant_type == 'client_credentials':
            clients = retrieve_clients_from_db()
            client_data = next((client for client in clients if client['client_id'] == client_id), None)

            if client_data and client_data['client_secret'] == client_secret: 
                return OAuth2Client(
                    client_id=client_id,
                    client_secret=client_secret,
                    grant_type=client_data.get('grant_type', 'client_credentials'),
                    scope=client_data.get('scope', 'read'),
                    permissions=client_data.get('permissions')
                )
            

        raise OAuth2Error(error='invalid_client', description='Client authentication failed.')

    def revoke_token(self, token):
        #will be used for cleaning abandonded tokens
        hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
        execute_query("""
            DELETE FROM tokens WHERE access_token = ? OR refresh_token = ?
        """, (hashed_token, hashed_token), commit=True)
        return {"message": "Token revoked successfully"}

    def get_scope(client_id):
        clients = retrieve_clients_from_db()
        client_data = next((client for client in clients if client['client_id'] == client_id), None)
        if not client_data:
            raise OAuth2Error(error="invalid_client", description="Client not found.")
        return client_data.get('scope', [])

    def get_permissions(client_id):
        clients = retrieve_clients_from_db()
        client_data = next((client for client in clients if client['client_id'] == client_id), None)
        if not client_data:
            raise OAuth2Error(error="invalid_client", description="Client not found.")
        return client_data.get('permissions', [])

    def validate_access_token(self, access_token):
        try:
            token_info = get_token_from_db(access_token)
            if not token_info:
                raise OAuth2Error(error="invalid_token", description="The provided token is invalid or revoked.")
            
            if is_token_expired(token_info['expires_at']):
                raise OAuth2Error(error="token_expired", description="The access token has expired.")
            
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload

        except jwt.ExpiredSignatureError:
            raise OAuth2Error(error="invalid_token", description="The access token has expired.")
        except jwt.InvalidTokenError:
            raise OAuth2Error(error="invalid_token", description="The access token is invalid.")
        except OAuth2Error as oauth_error:
            raise oauth_error
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise OAuth2Error(error="internal_error", description="An unexpected error occurred. Please try again later.")

    