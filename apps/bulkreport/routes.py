import logging
import re
import os
from flask import request, jsonify, g
from datetime import datetime
from pythonjsonlogger import jsonlogger
from . import blueprint
from .bulkprocess_api import load_bulk_meter_readings
from apps.apis.routes import check_permissions
from apps.apis.authServer import (
    authorization_server
)

# Ensure Logs directory exists
log_dir = 'Logs'
os.makedirs(log_dir, exist_ok=True)

# Configure logging to use JSON format
log_handler = logging.FileHandler(f'{log_dir}/bulk_app.log')  # Safe relative path
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
log_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)


def validate_token_and_set_context():
    """Validate the token and attach token_info to request context."""
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        logging.warning("Missing or malformed token")
        return jsonify({'error': 'missing_token', 'message': 'Authorization token is missing.'}), 401

    token = token.split(' ')[1]
    token_info = authorization_server.validate_token(token)
    if not token_info:
        logging.warning("Invalid or expired token")
        return jsonify({'error': 'invalid_token', 'message': 'The provided token is invalid or expired.'}), 401

    # Attach token info to the request context using `g`
    g.token_info = token_info
    return None


@blueprint.route('/public-api/meters/bulk-retrieve-readings', methods=['POST'])
@check_permissions
def bulk_retrieve_readings():
    """Retrieve bulk meter readings with logging and validation."""
    try:
        # Validate token and attach token_info to context
        token_validation_error = validate_token_and_set_context()
        if token_validation_error:
            return token_validation_error

        # Extract client_id from token info
        client_id = getattr(g, 'token_info', {}).get('client_id', 'Unknown')

        # Parse JSON body
        data = request.get_json()
        logical_device_names = data.get('logical_device_names')
        division_id = data.get('division_id')
        date = data.get('date')

        results = []

        # Validate logical device names
        if not logical_device_names or not isinstance(logical_device_names, list):
            logger.warning({
                "client_id": client_id,
                "error": "Invalid logical_device_names"
            })
            return jsonify({
                'error': 'missing_or_invalid_parameters',
                'message': 'Logical device names must be a non-empty list of alphanumeric strings.'
            }), 400

        # Check if logical_device_names exceed the maximum limit of 100
        if len(logical_device_names) > 100:
            logger.warning({
                "client_id": client_id,
                "error": "Too many logical_device_names"
            })
            return jsonify({
                'error': 'too_many_logical_device_names',
                'message': 'The maximum number of logical device names allowed is 100.'
            }), 400

        for name in logical_device_names:
            if not isinstance(name, str) or not re.match(r'^[A-Za-z0-9]+$', name):
                results.append({
                    "logical_device_name": name,
                    "reading_status": "validation_failed",
                    "message": f'Logical device name "{name}" is invalid. Only alphanumeric characters are allowed.'
                })

        # Validate division ID
        if not division_id or division_id not in ['DD1', 'DD2', 'DD3', 'DD4']:
            logger.warning({
                "client_id": client_id,
                "error": "Invalid division_id"
            })
            return jsonify({
                'error': 'invalid_division_id',
                'message': 'Division ID must be one of the following: DD1, DD2, DD3, DD4.'
            }), 400

        # Validate date
        if not date or not isinstance(date, str):
            logger.warning({
                "client_id": client_id,
                "error": "Invalid date"
            })
            return jsonify({
                'error': 'missing_or_invalid_date',
                'message': 'Date must be a non-empty string in YYYY-MM-DD format.'
            }), 400

        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            if date_obj.day != 1:
                logger.warning({
                    "client_id": client_id,
                    "error": "Date not first of month"
                })
                return jsonify({
                    'error': 'invalid_date',
                    'message': 'Date must be the first of the month (YYYY-MM-DD).'
                }), 400
        except ValueError:
            logger.warning({
                "client_id": client_id,
                "error": "Invalid date format"
            })
            return jsonify({
                'error': 'invalid_date_format',
                'message': 'Date must be in YYYY-MM-DD format.'
            }), 400

        # Process valid device names
        for name in logical_device_names:
            if name not in [result['logical_device_name'] for result in results if result['reading_status'] == "validation_failed"]:
                try:
                    result = load_bulk_meter_readings([name], division_id, date)
                    results.append({
                        "logical_device_name": name,
                        "reading_status": "success" if result else "unsuccessful",
                        "data": result[0] if result else None
                    })
                except Exception as e:
                    logger.error({
                        "client_id": client_id,
                        "error": f"Error retrieving reading for device {name}",
                        "exception": str(e)
                    })
                    results.append({
                        "logical_device_name": name,
                        "reading_status": "error",
                        "message": str(e)
                    })

        # Log successful access
        logger.info({
            "client_id": client_id,
            "action": "bulk_retrieve_readings",
            "retrieved_data": results
        })

        return jsonify({"result": results}), 200

    except Exception as e:
        client_id = getattr(g, 'token_info', {}).get('client_id', 'Unknown')
        logger.exception({
            "client_id": client_id,
            "error": "Unexpected error",
            "exception": str(e)
        })
        return jsonify({'error': 'internal_server_error', 'message': str(e)}), 500
