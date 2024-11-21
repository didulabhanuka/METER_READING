import json
import os
import hashlib
import base64
import secrets
import time
import logging
from authlib.oauth2.rfc6749 import OAuth2Error, AuthorizationServer
from authlib.oauth2.rfc6749.grants import ClientCredentialsGrant
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo


# Path to the JSON file where tokens will be saved
tokens_file = os.path.join(os.getcwd(), 'apps/apis/tokens.json')

class Client:
    def __init__(self, client_id, client_secret, grant_type, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.grant_type = grant_type
        self.scope = scope

    def check_grant_type(self, grant_type):
        return self.grant_type == grant_type

def load_clients_from_file(clients_file):
    if os.path.exists(clients_file):
        try:
            with open(clients_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f'Error decoding JSON from file: {e}')
            return []
    return []

def save_client_to_file(client_data, clients_file):
    try:
        if os.path.exists(clients_file):
            with open(clients_file, 'r') as f:
                clients = json.load(f)
        else:
            clients = []

        clients.append(client_data)

        with open(clients_file, 'w') as f:
            json.dump(clients, f, indent=4)
    except Exception as e:
        logging.error(f'Failed to save client data: {e}')

def load_tokens_from_file(tokens_file):
    if os.path.exists(tokens_file):
        try:
            with open(tokens_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f'Error decoding JSON from file: {e}')
            return {}
    return {}

def save_tokens_to_file(tokens, tokens_file):
    try:
        with open(tokens_file, 'w') as f:
            json.dump(tokens, f, indent=4)
    except Exception as e:
        logging.error(f'Failed to save tokens: {e}')

class MyAuthorizationServer(AuthorizationServer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_generator = self.default_token_generator  # Ensure the default generator is set

    def authenticate_client(self, request, grant_type):
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')

        if grant_type == 'refresh_token':
            return None

        if grant_type == 'client_credentials':
            if not client_id or not client_secret:
                raise OAuth2Error(
                    error='invalid_client',
                    description='Client authentication failed. Both client_id and client_secret are required.'
                )

            clients = load_clients_from_file('apps/apis/clients.json')

            client_data = next(
                (client for client in clients if client['client_id'] == client_id),
                None
            )

            if client_data and client_data['client_secret'] == client_secret:
                return Client(
                    client_id,
                    client_secret,
                    client_data.get('grant_type', 'client_credentials'),
                    client_data.get('scope', 'read')
                )
            
            raise OAuth2Error(
                error='invalid_client',
                description='Client authentication failed. Invalid client_id or client_secret.'
            )
        
        raise OAuth2Error(
            error='unsupported_grant_type',
            description=f'Grant type {grant_type} is not supported.'
        )

    def save_token(self, token, client=None, invalidate_previous=False):
        try:
            client_id = client.client_id if client else token['client_id']
            tokens = load_tokens_from_file(tokens_file)
            
            hashed_access_token = hashlib.sha256(token['access_token'].encode('utf-8')).hexdigest()
            hashed_refresh_token = hashlib.sha256(token['refresh_token'].encode('utf-8')).hexdigest()

            if client_id not in tokens:
                tokens[client_id] = []

            if invalidate_previous:
                tokens[client_id] = []

            new_token_entry = {
                "client_id": client_id,
                "access_token": hashed_access_token,
                "refresh_token": hashed_refresh_token,
                "expires_at": token['expires_at'],
                "scope": token.get('scope', 'read'),
                "usage_count": 5 if invalidate_previous or not any(entry['scope'] == token.get('scope', 'read') for entry in tokens[client_id]) else next(entry['usage_count'] for entry in tokens[client_id] if entry['scope'] == token.get('scope', 'read'))
            }

            token_replaced = False
            for i, entry in enumerate(tokens[client_id]):
                if entry['scope'] == new_token_entry['scope']:
                    tokens[client_id][i] = new_token_entry
                    token_replaced = True
                    break

            if not token_replaced:
                tokens[client_id].append(new_token_entry)

            save_tokens_to_file(tokens, tokens_file)

        except Exception as e:
            logging.error(f'Failed to save token: {e}')

    def validate_token(self, token, token_type='access'):
        try:
            hashed_token = hashlib.sha256(token.encode('utf-8')).hexdigest()
            tokens = load_tokens_from_file(tokens_file)

            for client_id, token_entries in tokens.items():
                for entry in token_entries:
                    if token_type == 'access' and entry['access_token'] == hashed_token:
                        if time.time() < entry['expires_at']:
                            return entry
                    elif token_type == 'refresh' and entry['refresh_token'] == hashed_token:
                        if entry['usage_count'] > 0:
                            return entry
            return None
        except Exception as e:
            logging.error(f'Failed to validate {token_type} token: {e}')
            return None

    def reduce_refresh_token_usage(self, client_id):
        try:
            tokens = load_tokens_from_file(tokens_file)

            if not tokens or client_id not in tokens:
                return

            token_entries = tokens[client_id]

            for entry in token_entries:
                entry['usage_count'] -= 1

                if entry['usage_count'] <= 0:
                    token_entries.remove(entry)

            save_tokens_to_file(tokens, tokens_file)

        except Exception as e:
            logging.error(f'Failed to reduce token usage: {e}')


    def invalidate_previous_tokens(self, client_id, tokens):
        try:
            if client_id in tokens:
                del tokens[client_id]
                save_tokens_to_file(tokens, tokens_file)
        except Exception as e:
            logging.error(f'Failed to invalidate previous tokens: {e}')

    def default_token_generator(self, client, grant_type, *args, **kwargs):
        try:
            random_bytes = secrets.token_bytes(32)
            access_token = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
            refresh_token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            expires_in = 3600
            expires_at = time.time() + expires_in
            scope = 'read'

            token = {
                'access_token': access_token,
                'token_type': 'bearer',
                'expires_in': expires_in,
                'expires_at': expires_at,
                'refresh_token': refresh_token,
                'scope': scope
            }

            return token
        except Exception as e:
            logging.error(f"Error in token generation: {e}")
            return None
    
    def generate_token(self, client, grant_type, *args, **kwargs):
        if not self.token_generator:
            self.token_generator = self.default_token_generator
        return self.token_generator(client, grant_type, *args, **kwargs)

    def handle_new_token(self, client, grant_type):
        token = self.generate_token(client, grant_type)
        self.save_token(token, client, invalidate_previous=True)
        return token

    def handle_refresh_token(self, refresh_token, provided_client_id):
        try:
            tokens = load_tokens_from_file(tokens_file)
            refresh_token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

            if provided_client_id in tokens:
                token_entries = tokens[provided_client_id]

                for entry in token_entries:
                    if entry.get('refresh_token') == refresh_token_hash:
                        if refresh_token == entry.get('access_token'):
                            return {'error': 'invalid_refresh_token_usage', 'message': 'Refresh token cannot be used as an access token.'}

                        new_token = self.default_token_generator(None, grant_type='refresh_token')

                        if new_token is None:
                            return {'error': 'token_generation_failed', 'message': 'Failed to generate new token.'}
                        
                        new_token['client_id'] = provided_client_id

                        self.save_token(new_token, client=None)
                        self.reduce_refresh_token_usage(provided_client_id)
                        
                        return new_token

            return {'error': 'invalid_or_expired_refresh_token', 'message': 'The provided refresh token is invalid or has expired.'}

        except Exception as e:
            logging.error(f'Error in handle_refresh_token: {e}')
            return {'error': 'internal_server_error', 'message': 'An internal server error occurred.'}


# Initialize the authorization server and register the grant type
authorization_server = MyAuthorizationServer()
authorization_server.register_grant(ClientCredentialsGrant)