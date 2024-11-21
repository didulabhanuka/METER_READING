# Standard Library Imports
import logging
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

# Local Application/Library Imports
from . import blueprint
from .bulkprocess_api import load_bulk_meter_readings
from apps.apis.routes import check_permissions  

@on_exception(expo, RateLimitException, max_tries=3)
@limits(calls=10, period=60)  # 10 requests per minute
@blueprint.route('/public-api/meters/bulk-retrieve-readings', methods=['POST'])
def bulk_retrieve_data():
    try:
        # Parse JSON body
        data = request.get_json()
        logical_device_names = data.get('logical_device_names', [])
        date = data.get('date')

        # Validate input parameters
        if not logical_device_names or not isinstance(logical_device_names, list):
            return jsonify({
                'error': 'missing_or_invalid_parameters',
                'message': 'Logical device names must be a non-empty list.'
            }), 400

        if not date:
            return jsonify({
                'error': 'missing_date',
                'message': 'Date parameter is required.'
            }), 400

        # Prepare results
        results = []

        for device_name in logical_device_names:
            try:
                # Call the function to load meter data for a single device
                meter_data = load_bulk_meter_readings([device_name], date)

                # Check if data retrieval is successful
                if meter_data:
                    results.append({
                        "logical_device_name": device_name,
                        "reading_status": "success",
                        "data": meter_data[0] if meter_data else None  # Assuming the first result for a single device
                    })
                else:
                    results.append({
                        "logical_device_name": device_name,
                        "reading_status": "unsuccess",
                        "data": None
                    })
            except Exception as e:
                # Handle any issues per device and log them
                logging.error(f"Error processing device {device_name}: {e}")
                results.append({
                    "logical_device_name": device_name,
                    "reading_status": "unsuccess",
                    "data": None
                })

        # Return the final results
        return jsonify({"result": results}), 200

    except ValueError as ve:
        logging.error("Value error during processing: %s", str(ve))
        return jsonify({'error': 'value_error', 'message': str(ve)}), 422
    except RateLimitException:
        return jsonify({'error': 'too_many_requests', 'message': 'Rate limit exceeded. Please try again later.'}), 429
    except Exception as e:
        logging.exception("An internal error occurred while processing the request: %s", str(e))
        return jsonify({'error': 'internal_error', 'message': 'An unexpected error occurred.'}), 500
