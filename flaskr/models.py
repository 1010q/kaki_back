from flaskr.app import db
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz
import jwt

japan_timezone = pytz.timezone('Asia/Tokyo')
def get_japan_time():
    return datetime.now(japan_timezone)

stars_table = db.Table('stars',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('starred', db.Boolean, default=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    token = db.Column(db.String(256), nullable=True, unique=True)
    profile_image = db.Column(db.Text, nullable=True, default=None)

    stars = db.relationship('Project', secondary=stars_table, backref=db.backref('stargazers'))
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_token(self):
        payload = {"user_id": self.id}
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm="HS256")
        self.token = token
        db.session.commit()
        return token

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=get_japan_time, nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tags = db.Column(db.PickleType, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stars = db.Column(db.Integer)
    star_count = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref=db.backref('projects', lazy=True))
    members = db.relationship('User', secondary='project_members', backref=db.backref('projects_as_member', lazy=True))
    commits = db.relationship('Commit', back_populates='project', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Project {self.name}>'

class ProjectMembers(db.Model):
    __tablename__ = 'project_members'
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

class Commit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=get_japan_time, nullable=False)
    commit_message = db.Column(db.String(256), nullable=False)
    commit_image = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    project = db.relationship('Project', back_populates='commits')
    user = db.relationship('User', backref=db.backref('commits', lazy=True))

    def __repr__(self):
        return f'<Commit {self.commit_message}>'

class CommitComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=get_japan_time, nullable=False)
    content = db.Column(db.Text, nullable=False)
    commit_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=get_japan_time, nullable=False)
    status = db.Column(db.String(20), default='pending')
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    commit_id = db.Column(db.Integer, db.ForeignKey('commit.id'), nullable=True)

    to_user = db.relationship('User', foreign_keys=[to_user_id], backref=db.backref('received_notifications', lazy=True))
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref=db.backref('sent_notifications', lazy=True))
    project = db.relationship('Project', backref=db.backref('notifications', lazy=True))
    commit = db.relationship('Commit', backref=db.backref('notifications', lazy=True))

    def __repr__(self):
        return f'<Notification {self.message}>'