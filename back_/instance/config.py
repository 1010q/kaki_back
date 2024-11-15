import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'miso893-shiru777-wakame3'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///instance/app.db'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024