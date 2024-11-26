import os
from flask_migrate import Migrate
from flask_minify import Minify
from sys import exit
from apps.config import config_dict
from apps import create_app, db
from apps.apis.authServer import init_db  # Import the init_db function

DEBUG = os.getenv('DEBUG', 'False')
print(f"DEBUG mode is set to: {DEBUG}")

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]

except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production]')

app = create_app(app_config)
Migrate(app, db)

# Initialize the database
init_db()  # Ensures the auth.db file and required tables are created

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)

if DEBUG:
    app.logger.info('DEBUG       = ' + str(DEBUG))
    app.logger.info('DBMS        = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT = ' + app_config.ASSETS_ROOT)

if __name__ == "__main__":
    # Check if HTTPS is enabled in the configuration
    if hasattr(app_config, 'SSL_CONTEXT') and app_config.SSL_CONTEXT:
        ssl_context = app_config.SSL_CONTEXT
        print("Starting Flask app on port http://127.0.0.1:5008...")
        app.run(host="0.0.0.0", port=5008)
    else:
        app.run(port=5005)
