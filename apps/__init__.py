from flask import Flask
from importlib import import_module

def register_blueprints(app):
    for module_name in ('apiserver', 'bulkmetering', 'ordinarymetering'):
        module = import_module(f'apps.{module_name}.routes')
        app.register_blueprint(module.blueprint)

def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    register_blueprints(app)
    return app
