import pymssql
from apps.config import Config
from typing import List, Dict
from datetime import datetime
import logging
import os
import json

# Define the log directory and log file path
log_dir = os.path.join(os.getcwd(), 'Logs')
log_file = os.path.join(log_dir, 'bulk_app.log')

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

def load_bulk_meter_readings(logical_device_names: List[str], division_id: str, date: str):
    try:
        # Validate and format date
        date_parts = datetime.strptime(date, "%Y-%m-%d").date()
        if date_parts.day != 1:
            raise ValueError("Date must be the first of the month.")

        # Convert logical device names list to a format suitable for SQL query
        device_names_str = ', '.join(f"'{name}'" for name in logical_device_names)

        query = f"""
        SELECT  
            mm.LogicalDeviceName AS "mtr_nbr",
            mrbb.DateTime AS "rdng_date",
            ROUND(mrbb.ActiveEnergyPluse, 0) AS "kwh_tot",
            ROUND(mrbb.ActiveEnergyTariff1Pluse, 0) AS "kwh_r1",
            ROUND(mrbb.ActiveEnergyTariff2Pluse, 0) AS "kwh_r2",
            ROUND(mrbb.ActiveEnergyTariff3Pluse, 0) AS "kwh_r3",
            CEILING(mrbb.MaxDemandPluse) AS "max_dmnd",
            mrbb.MaxDemandOccuringTimePluse AS "max_dmnd_Time",
            ROUND(mrbb.ReactiveEnergyPluse, 0) AS "kvarh_tot",
            ROUND(mrbb.ReactiveEnergyTariff1Pluse, 0) AS "kvarh_r1",
            ROUND(mrbb.ReactiveEnergyTariff2Pluse, 0) AS "kvarh_r2",
            ROUND(mrbb.ReactiveEnergyTariff3Pluse, 0) AS "kvarh_r3",
            ROUND(mrbb.ActiveEnergyMinus, 0) AS "kwh_exp_tot",
            ROUND(mrbb.ActiveEnergyTariff1Minus, 0) AS "kwh_r1_exp",
            ROUND(mrbb.ActiveEnergyTariff2Minus, 0) AS "kwh_r2_exp",
            ROUND(mrbb.ActiveEnergyTariff3Minus, 0) AS "kwh_r3_exp",
            CEILING(mrbb.MaxDemandMinus) AS "max_dmnd_exp",
            mrbb.MaxDemandOccuringTimeMinus AS "max_dmnd_exp_Time",
            ROUND(mrbb.ReactiveEnergyMinus, 0) AS "kvarh_exp_tot",
            ROUND(mrbb.ReactiveEnergyTariff1Minus, 0) AS "kvarh_r1_exp",
            ROUND(mrbb.ReactiveEnergyTariff2Minus, 0) AS "kvarh_r2_exp",
            ROUND(mrbb.ReactiveEnergyTariff3Minus, 0) AS "kvarh_r3_exp"
        FROM MeterReadingsBulkBilling mrbb 
        JOIN MeterMaster mm ON mm.MeterId = mrbb.MeterId 
        JOIN MeterAssignment ma ON mrbb.MeterId = ma.MeterId 
        WHERE mm.LogicalDeviceName IN ({device_names_str})
        AND mm.DivisionId = %s
        AND CAST(mrbb.DateTime AS DATE) = DATEFROMPARTS(%s, %s, %s)
        AND ma.AssetTypeId = 2;
        """

        # Extract year, month, and day from the date for DATEFROMPARTS
        year, month, day = date_parts.year, date_parts.month, date_parts.day

        with get_db_connection() as conn:
            with conn.cursor(as_dict=True) as cursor:
                cursor.execute(query, (division_id, year, month, day))
                results = cursor.fetchall()
                return results

    except ValueError as ve:
        logging.error("Invalid input value: %s", ve)
        return {'error': 'invalid_input', 'message': str(ve)}
    except Exception as e:
        logging.error("Database error: %s", e)
        return {'error': 'database_error', 'message': str(e)}