import os

class Config(object):

    basedir = os.path.abspath(os.path.dirname(__file__))

    # Set up the App SECRET_KEY
    SECRET_KEY = os.getenv('SECRET_KEY', '9#99maLvMKk2T4*tghA7og$m')

    HASH_ALGORITHM = 'HS256'
    # Assets Management
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')    
    
   # Database configuration
    SMART_METER_CONNECTION_PARAMS = {
        "server": "10.128.0.21",
        "user": "sacebhes",
        "password": "@563PYdjCa3s4Br",
        "database": "CEBHES",
    } 
    
    # Database configuration
    BREAKDOWN_ASSIST_CONNECTION_PARAMS = {
        "server": "10.128.0.21",
        #"user": "cebhes",
        "user": "rohes",
        #"password": "Hex%2021",
        "password": "lqOKRk1E5hb^^9lDyRuy",
        "database": "BreakdownAssist",
    }
    
    
    # Database configuration
    NCRE_CONNECTION_PARAMS = {
        "server": "10.128.0.21",
        #"user": "cebhes",
        "user": "rohes",
        #"password": "Hex%2021",
        "password": "lqOKRk1E5hb^^9lDyRuy",
        "database": "NCRE",
    }
    
    def print_debug_info(self):
        print("Config base directory:", self.basedir)
        print("Current working directory:", os.getcwd())

class ProductionConfig(Config):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 10

class DebugConfig(Config):
    DEBUG = True

# Load all possible configurations
config_dict = {
    'Production': ProductionConfig,
    'Debug'     : DebugConfig
}
