import os

class Config(object):

    basedir = os.path.abspath(os.path.dirname(__file__))

    # Set up the App SECRET_KEY
    SECRET_KEY = os.getenv('SECRET_KEY', '9#99maLvMKk2T4*tghA7og$m')

    # This will create a file in <app> FOLDER
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False 

    # Assets Management
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')    
    
    # AD Configuration
    AD_SERVER = '10.128.1.12'
    AD_DOMAIN = 'ceb.lk' 
    AD_SEARCH_BASE = 'dc=ceb,dc=local' 
    AD_GROUP_DN = 'CN=MDM' 

    # Database configuration
    SMART_METER_CONNECTION_PARAMS = {
        "server": "10.128.0.31",
        "user": "SA",
        "password": "Cebhes@2024#",
        "database": "CEBHES",
    } 
    
    # Database configuration
    BREAKDOWN_ASSIST_CONNECTION_PARAMS = {
        "server": "10.128.0.31",
        "user": "SA",
        "password": "Cebhes@2024#",
        "database": "BreakdownAssist",
    }
    
    # Database configuration
    NCRE_CONNECTION_PARAMS = {
        "server": "10.128.0.31",
        "user": "SA",
        "password": "Cebhes@2024#",
        "database": "NCRE",
    }
    
    def print_debug_info(self):
        print("Config base directory:", self.basedir)
        print("SQLite Database URI:", self.SQLALCHEMY_DATABASE_URI)
        print("Current working directory:", os.getcwd())

class ProductionConfig(Config):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 10

    # SSL Configuration
    SSL_CONTEXT = ('cert.pem', 'key.pem')

    #MySQL database
    #SQLALCHEMY_DATABASE_URI = '{}://{}:{}@{}:{}/{}'.format(
    #    os.getenv('DB_ENGINE'   , 'mysql'),
    #    os.getenv('DB_USERNAME' , 'hesback'),
    #    os.getenv('DB_PASS'     , 'Abc*123456'),
    #    os.getenv('DB_HOST'     , 'localhost'),
    #    os.getenv('DB_PORT'     , 10061),
    #    os.getenv('DB_NAME'     , 'Mysql')
    #)

class DebugConfig(Config):
    DEBUG = True
    SSL_CONTEXT = None  # No SSL in debug mode

# Load all possible configurations
config_dict = {
    'Production': ProductionConfig,
    'Debug'     : DebugConfig
}
