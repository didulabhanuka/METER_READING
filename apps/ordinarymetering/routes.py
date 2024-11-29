# Standard Library Imports
import logging
from functools import wraps

# Third-Party Library Imports
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

# Local Application/Library Imports
from . import blueprint
from apps.apiserver.routes import check_permissions
from .ordinaryprocess_api import load_meter_by_logical_device_number, validate_date_range


@on_exception(expo, RateLimitException, max_tries=3)
@limits(calls=10, period=60)  # 10 requests per minute
@blueprint.route('/retrieve-readings', methods=['POST'])
@check_permissions
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
            logging.warning(date_validation_result['message'])
            return jsonify(date_validation_result), 400

        # Check for missing parameters
        missing_params = [
            param for param in ['logical_device_name', 'divisionID', 'start_date', 'end_date']
            if data.get(param) is None
        ]
        if missing_params:
            logging.warning(f"Missing parameters: {', '.join(missing_params)}")
            return jsonify({
                'error': 'missing_parameters',
                'message': f'Missing parameters: {", ".join(missing_params)}'
            }), 400

        # Call the function to load meter data
        result = load_meter_by_logical_device_number(logical_device_name, divisionID, start_date, end_date)
        return jsonify({"result": result}), 200

    except ValueError as ve:
        logging.error(f"Value error during processing: {ve}")
        return jsonify({'error': 'value_error', 'message': str(ve)}), 422
    except RateLimitException:
        logging.warning("Rate limit exceeded")
        return jsonify({'error': 'too_many_requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    except Exception as e:
        logging.exception(f"An internal error occurred while processing the request: {e}")
        return jsonify({'error': 'internal_error', 'message': 'An unexpected error occurred.'}), 500
