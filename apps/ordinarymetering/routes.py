import logging
import os
from functools import wraps
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo
from . import blueprint
from .ordinaryprocess_api import load_meter_by_logical_device_number, validate_date_range

# Ensure Logs directory exists
log_dir = 'Logs'
os.makedirs(log_dir, exist_ok=True)

# Configure logging to use JSON format for secure_data route
secure_data_log_file = f'{log_dir}/ordinary_retrieve_readings.log'
secure_data_log_handler = logging.FileHandler(secure_data_log_file)  # Safe relative path
secure_data_log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
secure_data_log_handler.setFormatter(secure_data_log_formatter)

# Create a dedicated logger for the secure_data route
secure_data_logger = logging.getLogger('secure_data_logger')
secure_data_logger.setLevel(logging.INFO)
secure_data_logger.addHandler(secure_data_log_handler)


@on_exception(expo, RateLimitException, max_tries=3)
@limits(calls=10, period=60)  # 10 requests per minute
@blueprint.route('/retrieve-readings', methods=['POST'])
def secure_data():
    try:
        # Parse JSON body
        data = request.get_json()
        logical_device_name = data.get('logical_device_name')
        divisionID = data.get('divisionID')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # Validate date range
        date_validation_result = validate_date_range(start_date, end_date)
        if date_validation_result:
            secure_data_logger.warning(f"Date range validation failed: {date_validation_result['message']}")
            return jsonify(date_validation_result), 400

        # Check for missing parameters
        missing_params = [
            param for param in ['logical_device_name', 'divisionID', 'start_date', 'end_date']
            if data.get(param) is None
        ]
        if missing_params:
            secure_data_logger.warning(f"Missing parameters: {', '.join(missing_params)}")
            return jsonify({
                'error': 'missing_parameters',
                'message': f'Missing parameters: {", ".join(missing_params)}'
            }), 400

        # Call the function to load meter data
        result = load_meter_by_logical_device_number(logical_device_name, divisionID, start_date, end_date)

        # Log successful data retrieval
        secure_data_logger.info({
            'logical_device_name': logical_device_name,
            'divisionID': divisionID,
            'start_date': start_date,
            'end_date': end_date,
            'result': result
        })
        return jsonify({"result": result}), 200

    except ValueError as ve:
        secure_data_logger.error(f"Value error during processing: {ve}")
        return jsonify({'error': 'value_error', 'message': str(ve)}), 422
    except RateLimitException:
        secure_data_logger.warning("Rate limit exceeded")
        return jsonify({'error': 'too_many_requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    except Exception as e:
        secure_data_logger.exception(f"An internal error occurred while processing the request: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An unexpected error occurred.'}), 500
