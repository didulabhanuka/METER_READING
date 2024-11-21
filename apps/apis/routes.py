# Standard Library Imports
import os
import secrets
import logging

# Third-Party Library Imports
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo
from authlib.oauth2.rfc6749 import OAuth2Error
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Local Application/Library Imports
from . import blueprint
from .authServer import (
    authorization_server,
    save_client_to_file,
    load_clients_from_file,
)


# Initialize Flask-Limiter with an in-memory store (default)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Path to the JSON file where client details will be saved
clients_file = os.path.join(os.getcwd(), 'clients.json')

def check_permissions(f):
    def wrapper(*args, **kwargs):

        allClients = load_clients_from_file('apps/apis/clients.json')

        # Get the token from the Authorization header
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            logging.warning("Missing or malformed token")
            return jsonify({'error': 'missing_token', 'message': 'Authorization token is missing.'}), 401

        # Extract the actual token
        token = token.split(' ')[1]
        
        # Validate the token and get token info
        token_info = authorization_server.validate_token(token)
        if not token_info:
            logging.warning("Invalid or expired token")
            return jsonify({'error': 'invalid_token', 'message': 'The provided token is invalid or expired.'}), 401
        
        client_id = token_info['client_id']

        # Find the client permissions
        client = next((cred for cred in allClients if cred["client_id"] == client_id), None)
        
        if not client:
            logging.warning("Client not recognized")
            return jsonify({'error': 'forbidden', 'message': 'Client not recognized.'}), 403
        
        # Get the client's permissions
        permissions = client.get('permissions', {})
        
        # Check if the requested path and method are allowed
        if request.path not in permissions:
            logging.warning(f"Access denied for {client_id} to {request.path}: path not in permissions")
            return jsonify({'error': 'forbidden', 'message': 'You do not have access to this resource.'}), 403
        
        if request.method not in permissions[request.path]:
            logging.warning(f"Access denied for {client_id} to {request.path} with method {request.method}")
            return jsonify({'error': 'forbidden', 'message': 'You do not have access to this resource.'}), 403
        
        # If everything checks out, call the original function
        return f(*args, **kwargs)
    
    return wrapper


# Token Generation Endpoint
@blueprint.route('/public-api/OAuth/token', methods=['POST'])
@limiter.limit("4 per hour", key_func=lambda: request.form.get('client_id'))
def token():
    try:
        client_id = request.form.get('client_id')
        grant_type = request.form.get('grant_type')

        if not client_id:
            return jsonify({'error': 'invalid_client', 'message': 'Client ID is required.'}), 400

        client = authorization_server.authenticate_client(request, grant_type)
        if not client:
            return jsonify({'error': 'invalid_client', 'message': 'Client authentication failed.'}), 401

        new_token = authorization_server.handle_new_token(client, grant_type)
        return jsonify(new_token)

    except OAuth2Error as e:
        return jsonify({'error': str(e), 'message': 'OAuth2 Error occurred.'}), 400
    except Exception as e:
        logging.error(f'Unexpected error in token endpoint: {e}')
        return jsonify({'error': 'internal_server_error', 'message': 'An internal server error occurred.'}), 500

# Token Refresh Endpoint
@on_exception(expo, RateLimitException, max_tries=3)
@limits(calls=4, period=3600)  # 4 Token Refresh per hour
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
