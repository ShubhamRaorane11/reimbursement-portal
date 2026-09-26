"""
Flask application configuration.
Loads settings from environment variables via .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'reimbursement_portal')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'root123')

    # Automatically enable SSL when connecting to TiDB Cloud
    _ssl_params = ""
    if 'tidbcloud.com' in DB_HOST:
        _ssl_params = "&ssl_verify_cert=true&ssl_verify_identity=true"

    _default_db_url = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?charset=utf8mb4{_ssl_params}"
    )
    _db_url = os.environ.get('DATABASE_URL', _default_db_url)
    if _db_url.startswith('mysql://'):
        _db_url = _db_url.replace('mysql://', 'mysql+pymysql://', 1)
    if 'tidbcloud.com' in _db_url and 'ssl_verify_cert' not in _db_url:
        _db_url += '&ssl_verify_cert=true&ssl_verify_identity=true'

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }

    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours in seconds

    # File Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}

    # Tesseract OCR
    _default_tesseract = 'tesseract' if os.name != 'nt' else r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD', _default_tesseract)
