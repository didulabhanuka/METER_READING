import os
from flask_migrate import Migrate
from flask_minify import Minify
from sys import exit
from apps.config import config_dict
from apps import create_app, db
from apps.apis.authServer import init_db  # Import the init_db function

# Determine debug mode from environment variables (default is False)
DEBUG = (os.getenv('DEBUG', 'False') == 'True')
print(f"DEBUG mode is set to: {DEBUG}")

# Select configuration mode based on DEBUG
get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    # Load the appropriate configuration
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production]')

# Create Flask app with the selected configuration
app = create_app(app_config)
Migrate(app, db)

# Initialize the database (auth.db and required tables)
init_db()

# Apply HTML minification for production
if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)

# Log important app information
app.logger.info(f"DEBUG       = {DEBUG}")
app.logger.info(f"DBMS        = {app_config.SQLALCHEMY_DATABASE_URI}")
app.logger.info(f"ASSETS_ROOT = {app_config.ASSETS_ROOT}")

if __name__ == "__main__":
  
    if hasattr(app_config, 'SSL_CONTEXT') and app_config.SSL_CONTEXT:
        ssl_context = app_config.SSL_CONTEXT
        print("Starting Flask app with HTTPS on port 5080...")
        app.run(host="0.0.0.0", port=5080, ssl_context=ssl_context)
    else:
        print("Starting Flask app without HTTPS on port 5080...")
        app.run(host="0.0.0.0", port=5080)
