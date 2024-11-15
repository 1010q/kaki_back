from flask import app, request, jsonify
from flaskr.app import *
from flaskr.models import *
from werkzeug.utils import secure_filename
from functools import wraps
import jwt
import os


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'トークンが必要です'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'ユーザーが見つかりません'}), 404

            user_info = {
                "username": current_user.username,
                "user_id": current_user.id,
                "user_profile_image": current_user.profile_image
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'トークンの期限が切れています'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': '無効なトークンです'}), 401

        return f(current_user, *args, **kwargs)
    return decorated_function

#＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿ここからエンドポイント＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿

@app.route('/', methods=['GET'])
@token_required
def home(user):
    notifications = Notification.query.filter_by(user_id=user.id, status='pending').all()
    search_query = request.args.get('search', '')
    sort_order = request.args.get('sort', 'stars')

    project_query = Project.query.filter(Project.is_public == True)

    if search_query:
        project_query = project_query.filter(
            (Project.name.like(f'%{search_query}%') |
             Project.description.like(f'%{search_query}%'))
        )

    if sort_order == 'stars':
        project_query = project_query.join(stars_table).group_by(Project.id).order_by(db.func.count(stars_table.c.project_id).desc())
    else:
        project_query = project_query.order_by(Project.date_posted.desc())

    projects = project_query.all()

    project_data = [
        {"id": project.id, "name": project.name, "description": project.description, "created_user": project.user_id, "created_at": project.date_posted}
        for project in projects
    ]
    notification_data = [
        {"id": notification.id, "type": notification.type, "created_at": notification.created_at}
        for notification in notifications
    ]

    return jsonify({"projects": project_data, "notifications": notification_data, "user_id": user.id}),200


@app.route('/login', methods=['POST'])
@token_required
def login():#ログイン
    data = request.json
    user = User.query.filter_by(username=data.get("username")).first()

    if user and user.check_password(data.get("password")):
        token = user.generate_token()
        return  jsonify({"token": token}), 200
    else:
        return '', 401


@app.route('/logout', methods=['GET'])
@token_required
def logout():#ログアウト
    return '', 200


@app.route('/register', methods=['POST'])
def register():#登録
    data = request.json
    if data.get("password") != data.get("password2"):
        return jsonify({"message": "パスワードと確認用パスワードが一致しません。"}), 400
    
    if User.query.filter_by(username=User.username).first():
        return jsonify({"message": "このユーザー名は既に使用されています。"}), 409
    
    user = User(username=data.get("username"))
    user.set_password(data.get("password"))
    db.session.add(user)
    db.session.commit()
    token = user.generate_token()
    return jsonify({"token": token}), 201


@app.route('/profile/<int:user_id>', methods=['GET','POST'])
@token_required
def profile(user):
    if request.method == 'POST':
        profile_image = request.form.get('profile_image')
        
        
        if profile_image:
            image_binary = profile_image.read()
            user.profile_image = image_binary
            db.session.commit()
            return jsonify(message='プロフィール画像が更新されました。'), 200

    projects = Project.query.filter_by(user_id=user.id).all()
    
    response_data = {
        "username": user.username,
        "projects": [{
            "id": project.id,
            "name": project.name,
            "created_user":project.user_id,
            "latest_commit_image": project.commits[-1].commit_image
        } for project in projects],
        "profile_image": user.profile_image,
        "user_id":user.id
    }
    return jsonify(response_data), 200


@app.route('/makeproject', methods=['POST'])
@token_required
def make_project(user):
    data = request.json
    project_name = data.get('project_name')
    project_description = data.get('project_description')
    tags = data.get('tags', '').split(',')
    commit_message = data.get('commit_message')
    commit_image = request.form.get('commit_image')

    if commit_image:
        image_binary = commit_image.read()
    else:
        return '', 400

    new_project = Project(
        name=project_name,
        description=project_description,
        tags=tags,
        user_id=user.id
    )
    db.session.add(new_project)
    db.session.commit()

    new_commit = Commit(
        commit_message=commit_message,
        commit_image=image_binary,
        project_id=new_project.id,
        user_id=user.id
    )
    db.session.add(new_commit)
    db.session.commit()

    return jsonify(project_id=new_project.id), 201


@app.route('/project/<int:project_id>', methods=['GET', 'PATCH', 'DELETE'])
@token_required
def project_detail(user):
    project_id = request.view_args.get('project_id')
    project = Project.query.get_or_404(project_id)
    star_entry = db.session.execute(stars_table.select().where(stars_table.c.user_id == user.id,stars_table.c.project_id == project.id)).fetchone()
    
    if request.method == 'PATCH':
        action = request.json.get('action')
        if action == 'toggle_visibility':
            project.is_public = not project.is_public
            db.session.commit()
            return '', 200

        elif action == 'toggle_star':
            if star_entry:
                db.session.execute(
                    stars_table.delete().where(
                        stars_table.c.user_id == user.id,
                        stars_table.c.project_id == project.id
                    )
                )
                project.star_count -= 1
            else:
                db.session.execute(
                    stars_table.insert().values(user_id=user.id, project_id=project.id, starred=True)
                )
                project.star_count += 1

            db.session.commit()
            return '', 200

    elif request.method == 'DELETE':
        db.session.delete(project)
        db.session.commit()
        return '', 200

    latest_commit = Commit.query.filter_by(project_id=project.id).order_by(Commit.id.desc()).first()
    return jsonify(
        project_id=project.id,
        name=project.name,
        description=project.description,
        is_public=project.is_public,
        latest_commit_image=latest_commit.commit_image,
        created_user=project.user_id,
        project_member=project.members,
        project_star_count=project.star_count,
        star_entry=star_entry
    ), 200


@app.route('/project/<int:project_id>/invite', methods=['GET', 'POST'])
@token_required
def invite_user(project_id):
    project = Project.query.get_or_404(project_id)
    
    search_query = request.args.get('search', '')
    users = []
    
    if search_query:
        users = User.query.filter(User.username.contains(search_query)).all()

    if request.method == 'POST':
        user_id = request.json.get('user_id')
        user_to_invite = User.query.get(user_id)
        
        if user_to_invite:
            notification = Notification(
                project_name=project.name,
                user_id=user_to_invite.id,
                project_id=project.id,
                type="invite"
            )
            db.session.add(notification)
            db.session.commit()
            return jsonify(message=f'{user_to_invite.username}が招待されました。'), 200
        
        return '', 404

    return jsonify(project_member=project.members, users=[{"id": user.id, "username": user.username, "user_image": user.profile_image} for user in users]), 200


@app.route('/project/<int:project_id>/commit', methods=['POST'])
@token_required
def commit(user, project_id):
    project = Project.query.get_or_404(project_id)

    commit_message = request.json.get('commit_message')
    commit_image = request.files.get('commit_image')
    
    if commit_image:
        filename = secure_filename(commit_image.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        commit_image.save(filepath)
    else:
        return '', 400

    new_commit = Commit(
        commit_message=commit_message,
        commit_image=filepath,
        project_id=project.id,
        user_id=user.id
    )
    db.session.add(new_commit)
    db.session.commit()

    users = project.members
    for member in users:
        if member.id != user.id:
            notification = Notification(
                created_at=notification.created_at,
                type="commit",
                user_id=member.id,
                project_id=project.id,
                commit_id=commit.id
            )
            db.session.add(notification)
    db.session.commit()

    return '', 201


@app.route('/project/<int:project_id>/commits')
@token_required
def commits(project_id):
    project = Project.query.get_or_404(project_id)
    commits = Commit.query.filter_by(project_id=project.id).order_by(Commit.id.desc()).all()

    return jsonify(commits=[{
        "id": commit.id,
        "commit_message": commit.commit_message,
        "commit_image": commit.commit_image,
        "created_at": commit.date_posted
    } for commit in commits]), 200


@app.route('/project/<int:project_id>/commit/<int:commit_id>', methods=['GET', 'POST'])
@token_required
def commit_detail(user, project_id, commit_id):
    project = Project.query.get_or_404(project_id)
    commit = Commit.query.get_or_404(commit_id)
    
    if request.method == 'POST':
        data = request.get_json()
        content = data.get('content')
        
        if content:
            comment = CommitComment(content=content, commit_id=commit.id, user_id=user.id)
            db.session.add(comment)
            db.session.commit()

            users = project.members
            for member in users:
                if member.id != user.id:
                    notification = Notification(
                        created_at=notification.created_at,
                        type="comment",
                        commit_message=commit.commit_message,
                        project_name=project.name,
                        user_id=member.id,
                        project_id=project.id,
                        commit_id=commit.id,
                    )
                    db.session.add(notification)
            db.session.commit()

            return '', 200
        else:
            return '', 400

    comments = CommitComment.query.filter_by(commit_id=commit_id).all()
    comment_data = [{
        'id': comment.id,
        'content': comment.content,
        'created_at': comment.created_at,
        'user': {
            'id': comment.user.id,
            'username': comment.user.username
        }
    } for comment in comments]

    return jsonify(
        project_id=project.id,
        project_name=project.name,
        commit_id=commit.id,
        commit_message=commit.commit_message,
        commit_image=commit.commit_image,
        created_at=commit.created_at,
        comments=comment_data
    ), 200
#__________________________________通知_________________________________________

@app.route('/notification/<int:notification_id>/respond/<string:response>', methods=['PATCH'])
@token_required
def respond_to_invitation(user, notification, response):
    data = request.get_json()
    response = data.get('response')
    notification = Notification.query.filter_by(user_id=user.id).all()
    
    if response == 'accept':
        notification.status = 'accepted'
        project = notification.project
        project.members.append(user)
        db.session.commit()
        return '', 200
    
    elif response == 'decline':
        notification.status = 'declined'
        db.session.commit()
        return '', 200