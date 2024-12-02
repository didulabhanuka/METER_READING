import jwt
from functools import wraps
from flask import request, jsonify, g
from apps.config import Config
from apps.apiserver.authServer import OAuth2AuthorizationServer, OAuth2Error
from functools import wraps

# Constants
SECRET_KEY = Config.SECRET_KEY
ALGORITHM = Config.HASH_ALGORITHM
AUTH_HEADER = "Authorization"
BEARER_PREFIX = "Bearer"

def extract_access_token():
    """Extract the access token from the request's Authorization header."""
    auth_header = request.headers.get(AUTH_HEADER, "")
    if not auth_header.startswith(BEARER_PREFIX):
        return None
    return auth_header[len(BEARER_PREFIX):].strip()

def decode_token(token):
    """Decode the JWT token and handle potential errors."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("token_expired")
    except jwt.InvalidTokenError:
        raise ValueError("invalid_token")

def handle_error(error_key, description, status_code):
    """Return a standardized error response."""
    # Optional: Add logging for errors
    # logger.error(f"Error: {error_key}, Description: {description}")
    return jsonify(error=error_key, description=description), status_code

def requires_scope(required_scope):
    """Decorator to check if the client has the required scope (endpoint access)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = extract_access_token()
            if not token:
                return handle_error("missing_token", "Authorization token is required.", 401)
            
            try:
                payload = decode_token(token)
                client_id = payload.get("client_id")
                token_scope = OAuth2AuthorizationServer.get_scope(client_id) or []
                
                if required_scope not in token_scope:
                    return handle_error("insufficient_scope", f"Required scope: {required_scope}", 403)
            except ValueError as e:
                error_map = {
                    "token_expired": ("The access token has expired.", 401),
                    "invalid_token": ("The access token is invalid.", 401)
                }
                return handle_error(e.args[0], *error_map.get(e.args[0], ("Unknown error.", 400)))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def requires_permission(required_permission):
    """Decorator to check if the client has the required permission (read/write)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = extract_access_token()
            if not token:
                return handle_error("missing_token", "Authorization token is required.", 401)
            
            try:
                payload = decode_token(token)
                client_id = payload.get("client_id")
                token_permissions = OAuth2AuthorizationServer.get_permissions(client_id) or []
                
                if required_permission not in token_permissions:
                    return handle_error("insufficient_permission", f"Required permission: {required_permission}", 403)
            except ValueError as e:
                error_map = {
                    "token_expired": ("The access token has expired.", 401),
                    "invalid_token": ("The access token is invalid.", 401)
                }
                return handle_error(e.args[0], *error_map.get(e.args[0], ("Unknown error.", 400)))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def extract_and_validate_token():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.lower().startswith('bearer '):
        return None, {'error': 'missing_token', 'message': 'Authorization token is missing or improperly formatted.'}, 401
    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None, {'error': 'empty_token', 'message': 'Authorization token is empty.'}, 401
    try:
        token_info = OAuth2AuthorizationServer.validate_access_token(None, token)
        if not token_info:
            raise ValueError('invalid_token')
        return token_info, None, None
    except jwt.ExpiredSignatureError:
        return None, {'error': 'token_expired', 'message': 'The access token has expired.'}, 401
    except jwt.InvalidTokenError:
        return None, {'error': 'invalid_token', 'message': 'The provided token is invalid.'}, 401
    except OAuth2Error as e:
        return None, {'error': e.error, 'message': e.description}, 401
    except ValueError as e:
        if str(e) == 'invalid_token':
            return None, {'error': 'invalid_token', 'message': 'The provided token is invalid.'}, 401
        return None, {'error': 'internal_error', 'message': 'An internal server error occurred.'}, 500
    except Exception as e:
        return None, {'error': 'internal_error', 'message': 'An internal server error occurred.'}, 500

def validate_token_and_set_context(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token_info, error_response, status_code = extract_and_validate_token()
        if error_response:
            return jsonify(error_response), status_code
        g.token_info = token_info
        return f(*args, **kwargs)
    return decorated_function

