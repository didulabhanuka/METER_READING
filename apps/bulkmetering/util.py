import re
from flask import request, jsonify
from apps.apiserver.authServer import OAuth2AuthorizationServer

from datetime import datetime

def validate_logical_device_names(logical_device_names):
    if not logical_device_names or not isinstance(logical_device_names, list):
        return False, 'Logical device names must be a non-empty list of alphanumeric strings.'
    if len(logical_device_names) > 100:
        return False, 'The maximum number of logical device names allowed is 100.'
    invalid_names = [name for name in logical_device_names if not isinstance(name, str) or not re.match(r'^[A-Za-z0-9]+$', name)]
    return invalid_names, None

def validate_division_id(division_id):
    valid_divisions = ['DD1', 'DD2', 'DD3', 'DD4']
    if division_id not in valid_divisions:
        return False, 'Division ID must be one of DD1, DD2, DD3, DD4.'
    return True, ''


def validate_date(date):
    if not date or not isinstance(date, str):
        return False, 'Date must be a non-empty string in YYYY-MM-DD format.'
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        if date_obj.day != 1:
            return False, 'Date must be the first of the month (YYYY-MM-DD).'
    except ValueError:
        return False, 'Date must be in YYYY-MM-DD format.'
    return True, None