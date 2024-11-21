# Standard Library Imports
import logging
from flask import request, jsonify
from ratelimit import limits, RateLimitException
from backoff import on_exception, expo

# Local Application/Library Imports
from . import blueprint
from .bulkprocess_api import load_bulk_meter_readings
from apps.apis.routes import check_permissions  

@blueprint.route('/public-api/meters/bulk-retrieve-readings', methods=['POST'])
def bulk_retrieve_readings():
    try:
        # Parse JSON body
        data = request.get_json()
        logical_device_names = data.get('logical_device_names', [])
        division_id = data.get('division_id')
        date = data.get('date')

        # Validate input parameters
        if not logical_device_names or not isinstance(logical_device_names, list):
            return jsonify({
                'error': 'missing_or_invalid_parameters',
                'message': 'Logical device names must be a non-empty list.'
            }), 400
        if not division_id:
            return jsonify({
                'error': 'missing_division_id',
                'message': 'Division ID is required.'
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
                # Call the bulk meter readings function for each device
                result = load_bulk_meter_readings([device_name], division_id, date)

                # Check if data retrieval is successful
                if result:
                    results.append({
                        "logical_device_name": device_name,
                        "reading_status": "success",
                        "data": result[0] if result else None  # Assuming a single result per device
                    })
                else:
                    results.append({
                        "logical_device_name": device_name,
                        "reading_status": "unsuccess",
                        "data": None
                    })
            except Exception as e:
                logging.error(f"Error processing device {device_name}: {e}")
                results.append({
                    "logical_device_name": device_name,
                    "reading_status": "unsuccess",
                    "data": None
                })

        # Return the final results
        return jsonify({"result": results}), 200

    except Exception as e:
        logging.exception("Unexpected error occurred while processing request.")
        return jsonify({'error': 'internal_server_error', 'message': str(e)}), 500
