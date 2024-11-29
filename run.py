import os
from sys import exit
from apps.config import config_dict
from apps import create_app
from apps.apiserver.authServer import init_db

DEBUG = (os.getenv('DEBUG', 'False') == 'True')
print(f"DEBUG mode is set to: {DEBUG}")

get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production]')

app = create_app(app_config)

app.logger.info(f"DEBUG       = {DEBUG}")
app.logger.info(f"ASSETS_ROOT = {app_config.ASSETS_ROOT}")

if __name__ == "__main__":
    print("Starting Flask app on port 5080...")
    app.run(host="0.0.0.0", port=5080)
