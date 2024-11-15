from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)
app.config.from_pyfile('/opt/render/project/src/instance/config.py')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from flaskr.models import *
from flaskr.views import *

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()
