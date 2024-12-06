import pymssql
from apps.config import Config
from typing import List, Dict
from datetime import datetime 
import logging
import os
import json

# Define the log directory and log file path
log_dir = os.path.join(os.getcwd(), 'Logs')
log_file = os.path.join(log_dir, 'ordinary_retrieve_readings.log')

# Database configuration
SMART_METER_CONNECTION_PARAMS = Config.SMART_METER_CONNECTION_PARAMS
BREAKDOWN_ASSIST_CONNECTION_PARAMS = Config.BREAKDOWN_ASSIST_CONNECTION_PARAMS

def get_db_connection():
    return pymssql.connect(
        server=SMART_METER_CONNECTION_PARAMS['server'],
        user=SMART_METER_CONNECTION_PARAMS['user'],
        password=SMART_METER_CONNECTION_PARAMS['password'],
        database=SMART_METER_CONNECTION_PARAMS['database'],
    )
    
def get_db_connection_BA():
    return pymssql.connect(
        server=BREAKDOWN_ASSIST_CONNECTION_PARAMS['server'],
        user=BREAKDOWN_ASSIST_CONNECTION_PARAMS['user'],
        password=BREAKDOWN_ASSIST_CONNECTION_PARAMS['password'],
        database=BREAKDOWN_ASSIST_CONNECTION_PARAMS['database'],
    )



# Define or adapt this class based on the new result structure
class Customer:
    def __init__(self, Name = None, Address = None, AreaID = None):
        self.Name = Name
        self.Address = Address
        self.AreaID = AreaID


def validate_date_range(start_date: str, end_date: str):
    try:
        # Convert string dates to datetime objects
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Check if start date is less than end date
        if start_date_obj >= end_date_obj:
            return {
                'error': 'invalid_date_range',
                'message': 'Start date must be less than end date.'
            }
        
        # Check if the duration exceeds 40 days
        duration = (end_date_obj - start_date_obj).days
        if duration > 40:
            return {
                'error': 'duration_exceeded',
                'message': 'Duration between start date and end date must not exceed 40 days.'
            }

        return None  # Return None if both checks pass

    except ValueError as ve:
        return {
            'error': 'invalid_date_format',
            'message': f'Invalid date format: {str(ve)}'
        }




def load_meter_by_logical_device_number(logical_device_name: str, divisionID: str, start_date: str, end_date: str):
    # Convert date strings to a suitable format
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as ve:
        logging.error("Date format error: %s", ve)
        return {'error': 'invalid_date_format', 'message': str(ve)}

    # Load metering related columns from JSON file
    try:
        with open('apps/apis/serve_meter_readings.json', 'r') as f:
            json_data = json.load(f)
            metering_related_columns = json_data['MeteringRelated']
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error("Error reading JSON file: %s", e)
        return {'error': 'json_error', 'message': str(e)}

    # Construct the SQL SELECT statement with only metering-related columns
    selected_columns = ', '.join(metering_related_columns)
    
    query = f"""
            SELECT {selected_columns}
            FROM MeterReading mr
            JOIN MeterMaster mm ON mr.MeterId = mm.MeterId 
            WHERE mm.LogicalDeviceName = %s
            AND mm.DivisionID = %s
            AND mr.DateTime BETWEEN %s AND %s;
            """
    try:
        with get_db_connection() as conn:
            with conn.cursor(as_dict=True) as cursor:
                cursor.execute(query, (logical_device_name, divisionID, start_date, end_date))
                result = cursor.fetchall()  # Use fetchall to get all results
                return result  # Return results list, even if empty
    except Exception as e:
        logging.error("Error executing query: %s", e)
        return {'error': 'database_error', 'message': str(e)}  # Return error message as a dictionary


