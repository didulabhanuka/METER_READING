from flask import Blueprint

blueprint = Blueprint(
    'bulkreport_blueprint',
    __name__,
    url_prefix='/public-api/meters/bulk'
)