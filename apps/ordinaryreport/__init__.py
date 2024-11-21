from flask import Blueprint

blueprint = Blueprint(
    'ordinaryreport_blueprint',
    __name__,
    url_prefix='/ordinaryreport'
)
