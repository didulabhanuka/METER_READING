import logging
import os
from flask import request, jsonify, g
from pythonjsonlogger import jsonlogger
from apps.bulkmetering import blueprint
from apps.bulkmetering.bulkprocess_api import load_bulk_meter_readings
from apps.apiserver.decorators import requires_permission, requires_scope, validate_token_and_set_context
from apps.bulkmetering.util import validate_date, validate_logical_device_names, validate_division_id

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


@blueprint.route('/retrieve-readings', methods=['POST'])
@validate_token_and_set_context
@requires_scope("retrieve-readings")
@requires_permission("read")
def bulk_retrieve_readings():
    try:
        
        # Extract client_id from token info
        client_id = getattr(g, 'token_info', {}).get('client_id', 'Unknown')

        # Parse JSON body
        data = request.get_json()

        required_params = ['logical_device_names', 'division_id', 'date']
        missing_params = [param for param in required_params if param not in data]

        if missing_params:
            return jsonify({
                'error': 'missing_parameters',
                'message': f'Missing parameters: {", ".join(missing_params)}'
            }), 400

        logical_device_names = data['logical_device_names']
        division_id = data['division_id']
        date = data['date']

        results = []

        # Validate logical device names
        invalid_names, message = validate_logical_device_names(logical_device_names)
        if invalid_names:
            logger.warning({"client_id": client_id, "error": "Invalid logical_device_names", "invalid_names": invalid_names})
            #return jsonify({'error': 'invalid_logical_device_names', 'message': message}), 400

        # Validate division ID
        valid, message = validate_division_id(division_id)
        if not valid:
            logger.warning({"client_id": client_id, "error": "Invalid division_id", "message": message})
            return jsonify({'error': 'invalid_division_id', 'message': message}), 400

        # Validate date
        valid, message = validate_date(date)
        if not valid:
            logger.warning({"client_id": client_id, "error": "Invalid date", "message": message})
            return jsonify({'error': 'invalid_date', 'message': message}), 400

        # Process valid device names
        for name in logical_device_names:
            try:
                if name not in invalid_names:
                    result = load_bulk_meter_readings([name], division_id, date)
                    results.append({
                        "logical_device_name": name,
                        "reading_status": "success" if result else "unsuccessful",
                        "data": result[0] if result else None
                    })
                else:
                    results.append({
                        "logical_device_name": name,
                        "reading_status": "validation_failed",
                        "message": f'Logical device name "{name}" is invalid. Only alphanumeric characters are allowed.'
                    })
            except Exception as e:
                logger.error({"client_id": client_id, "error": f"Error retrieving reading for device {name}", "exception": str(e)})
                results.append({
                    "logical_device_name": name,
                    "reading_status": "error",
                    "message": str(e)
                })

        # Log successful access
        logger.info({"client_id": client_id, "action": "bulk_retrieve_readings", "retrieved_data": results})

        return jsonify({"result": results}), 200

    except Exception as e:
        logger.exception({"client_id": getattr(g, 'token_info', {}).get('client_id', 'Unknown'), "error": "Unexpected error", "exception": str(e)})
        return jsonify({'error': 'internal_server_error', 'message': str(e)}), 500
