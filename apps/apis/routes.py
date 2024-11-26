import os
import secrets
import logging
import sqlite3
import json
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo
from authlib.oauth2.rfc6749 import OAuth2Error
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from . import blueprint
from .authServer import (
    authorization_server,
    save_client_to_db,
    load_clients_from_db,
)

# Initialize Flask-Limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def check_permissions(f):
    def wrapper(*args, **kwargs):
        all_clients = load_clients_from_db()

        # Get the token from the Authorization header
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            logging.warning("Missing or malformed token")
            return jsonify({'error': 'missing_token', 'message': 'Authorization token is missing.'}), 401

        token = token.split(' ')[1]
        token_info = authorization_server.validate_token(token)
        if not token_info:
            logging.warning("Invalid or expired token")
            return jsonify({'error': 'invalid_token', 'message': 'The provided token is invalid or expired.'}), 401

        client_id = token_info['client_id']
        client = next((cred for cred in all_clients if cred["client_id"] == client_id), None)
        if not client:
            logging.warning("Client not recognized")
            return jsonify({'error': 'forbidden', 'message': 'Client not recognized.'}), 403

        # Validate permissions
        permissions = client.get('permissions', {})
        if request.path not in permissions or request.method not in permissions[request.path]:
            logging.warning(f"Access denied for {client_id} to {request.path} with method {request.method}")
            return jsonify({'error': 'forbidden', 'message': 'You do not have access to this resource.'}), 403

        return f(*args, **kwargs)
    return wrapper

@blueprint.route('/public-api/OAuth/token', methods=['POST'])
@limiter.limit("4 per hour", key_func=lambda: request.form.get('client_id'))
def token():
    try:
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')
        grant_type = request.form.get('grant_type', 'client_credentials')

        if not client_id or not client_secret:
            return jsonify({'error': 'invalid_client', 'message': 'Client ID and Client Secret are required.'}), 400

        # Authenticate the client
        client = authorization_server.authenticate_client(request, grant_type)
        if not client:
            return jsonify({'error': 'invalid_client', 'message': 'Client authentication failed.'}), 401

        # Generate a new token
        new_token = authorization_server.handle_new_token(client, grant_type)
        return jsonify(new_token)

    except OAuth2Error as e:
        return jsonify({'error': str(e), 'message': 'OAuth2 Error occurred.'}), 400
    except Exception as e:
        logging.error(f'Unexpected error in token endpoint: {e}')
        return jsonify({'error': 'internal_server_error', 'message': 'An internal server error occurred.'}), 500


@on_exception(expo, RateLimitException, max_tries=3)
@limits(calls=4, period=3600)
@blueprint.route('/public-api/OAuth/token/refresh', methods=['POST'])
def refresh_token():
    try:
        client_id = request.form.get('client_id')
        refresh_token = request.form.get('refresh_token')

        if not client_id:
            return jsonify({'error': 'invalid_client', 'message': 'Client ID is required.'}), 400

        new_token = authorization_server.handle_refresh_token(refresh_token, client_id)
        if 'error' in new_token:
            return jsonify(new_token), 401
        return jsonify(new_token)

    except RateLimitException:
        return jsonify({'error': 'too_many_requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    except Exception as e:
        logging.error(f'Unexpected error in refresh token endpoint: {e}')
        return jsonify({'error': 'internal_server_error', 'message': 'An internal server error occurred.'}), 500

@blueprint.route('/public-api/OAuth/create-client', methods=['POST'])
def create_client():
    client_id = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)

    permissions = request.json.get('permissions', {})  # Get permissions from the request
    client_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "permissions": permissions
    }
    save_client_to_db(client_data)

    return jsonify(client_data)

@blueprint.route('/protected-resource', methods=['GET', 'POST'])
@check_permissions
def protected_resource():
    return jsonify({"message": "Access granted!"})
