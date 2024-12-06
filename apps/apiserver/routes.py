import logging
import os
from pythonjsonlogger import jsonlogger
from flask import Blueprint, request, jsonify, g
from authlib.oauth2.rfc6749 import OAuth2Error
from authlib.oauth2.rfc6749.grants import ClientCredentialsGrant
from werkzeug.exceptions import BadRequest
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from apps.apiserver.authServer import OAuth2AuthorizationServer
from apps.apiserver.authServer import initialize_database
from apps.apiserver import blueprint

# Ensure Logs directory exists
log_dir = 'Logs'
os.makedirs(log_dir, exist_ok=True)

# Configure logging to use JSON format for token-related routes
token_log_file = f'{log_dir}/token_operations.log'
token_log_handler = logging.FileHandler(token_log_file)  # Safe relative path
token_log_formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
token_log_handler.setFormatter(token_log_formatter)

# Create a dedicated logger for token operations
token_logger = logging.getLogger('token_operations_logger')
token_logger.setLevel(logging.INFO)
token_logger.addHandler(token_log_handler)

authorization_server = OAuth2AuthorizationServer()
initialize_database()
authorization_server.register_grant(ClientCredentialsGrant)

# Initialize Flask-Limiter for rate limiting
limiter = Limiter(key_func=get_remote_address)

@blueprint.route('/token', methods=['POST'])
@limiter.limit("200 per day")
def issue_token():
    try:
        # Retrieve client credentials from the request
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')

        # Log the token request attempt
        token_logger.info({
            'client_id': client_id,
            'action': 'issue_token',
            'status': 'request_received'
        })

        # Authenticate the client
        client = authorization_server.authenticate_client(request, 'client_credentials')
        
        # Generate and return the JWT access token and refresh token
        token_response = authorization_server.generate_jwt_token(client, 5)
        g.token_info = token_response
        
        # Log the successful token generation
        token_logger.info({
            'client_id': client_id,
            'action': 'issue_token',
            'status': 'success',
            'token_info': token_response
        })
        
        return jsonify(token_response)

    except OAuth2Error as e:
        token_logger.error({
            'client_id': client_id,
            'action': 'issue_token',
            'status': 'error',
            'error': e.error,
            'description': e.description
        })
        return jsonify(error=e.error, description=e.description), 400
    except BadRequest as e:
        token_logger.error({
            'client_id': client_id,
            'action': 'issue_token',
            'status': 'error',
            'error': 'invalid_request',
            'description': str(e)
        })
        return jsonify(error='invalid_request', description=str(e)), 400

@blueprint.route('/token/refresh', methods=['POST'])
def refresh_token():
    try:
        refresh_token = request.form.get('refresh_token')
        
        # Log the token refresh request
        token_logger.info({
            'refresh_token': refresh_token,
            'action': 'refresh_token',
            'status': 'request_received'
        })
        
        new_tokens = authorization_server.refresh_access_token(str(refresh_token))
        g.token_info = new_tokens
        
        # Log the successful token refresh
        token_logger.info({
            'refresh_token': refresh_token,
            'action': 'refresh_token',
            'status': 'success',
            'new_tokens': new_tokens
        })
        
        return jsonify(new_tokens)
    except OAuth2Error as e:
        token_logger.error({
            'refresh_token': refresh_token,
            'action': 'refresh_token',
            'status': 'error',
            'error': e.error,
            'description': e.description
        })
        return jsonify(error=e.error, description=e.description), 400
