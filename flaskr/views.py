from flask import app, request, jsonify
from flaskr.app import *
from flaskr.models import *
from functools import wraps
import base64
import jwt

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            class GuestUser:
                id = None
                username = None
                profile_image = None
            guest_user = GuestUser()

            return f(guest_user, *args, **kwargs)

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'ユーザーが見つかりません'}), 404

        except jwt.InvalidTokenError:
            return jsonify({'message': '無効なトークンです'}), 401

        return f(current_user, *args, **kwargs)
    return decorated_function

#＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿ここからエンドポイント＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿

@app.route('/userinfo', methods=['GET'])
@token_required
def userinfo(user):
    current_user = {
                "username": user.username,
                "user_id": user.id,
                "profile_image": user.profile_image
            }
    return jsonify(current_user), 200


@app.route('/', methods=['GET'])
@token_required
def home(current_user):
    notifications = Notification.query.filter_by(to_user_id=current_user.id, status='pending').all()
    search_query = request.args.get('search', '')
    sort_order = request.args.get('sort', 'stars')

    project_query = Project.query.filter(Project.is_public == True)

    if search_query:
        project_query = project_query.filter(
            (Project.name.like(f'%{search_query}%') |
             Project.description.like(f'%{search_query}%'))
        )

    if sort_order == 'stars':
        project_query = project_query.order_by(Project.star_count.desc(), Project.created_at.desc())
    else:
        project_query = project_query.order_by(Project.created_at.desc())

    projects = project_query.all()
    latest_commits = Commit.query.filter(Commit.project_id.in_([project.id for project in projects])) \
    .order_by(Commit.project_id, Commit.id.desc()).all()

    latest_commit_dict = {}
    for commit in latest_commits:
        latest_commit_dict[commit.project_id] = commit

    project_data = [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "created_username": project.user.username,
            "created_user_id": project.user_id,
            "created_user_profile_image": project.user.profile_image,
            "created_at": project.created_at,
            "latest_commit_image": latest_commit_dict.get(project.id).commit_image if latest_commit_dict.get(project.id) else ''
        }
        for project in projects
    ]
    notification_data = [
        {
            "id": notification.id,
            "type": notification.type,
            "created_at": notification.created_at,
            "from_user": {
                "username": notification.from_user.username,
                "profile_image": notification.from_user.profile_image,
                "user_id": notification.from_user.id
            },
            "project": {
                "name": notification.project.name,
                "project_id": notification.project.id,
                 "project_star_count": notification.project.star_count,
            },
            "commit": {
                "commit_id": notification.commit.id if notification.commit else None,
                "message": notification.commit.commit_message if notification.commit else None,
                "image": notification.commit.commit_image if notification.commit else None
            }
        }
        for notification in notifications
    ]

    return jsonify({"projects": project_data, "notifications": notification_data, "user_id": current_user.id}),200


@app.route('/login', methods=['POST'])
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
def register():  # 登録
    data = request.json

    if data.get("password") != data.get("password2"):
        return jsonify({"message": "パスワードと確認用パスワードが一致しません。"}), 400

    username = data.get("username")
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "このユーザー名は既に使用されています。"}), 409

    user = User(username=username)
    user.set_password(data.get("password"))
    db.session.add(user)
    db.session.commit()

    token = user.generate_token()
    return jsonify({"token": token}), 201


@app.route('/profile/<int:user_id>', methods=['GET','POST'])
@token_required
def profile(current_user, user_id):
    user = User.query.get(user_id)
    if request.method == 'POST':
        profile_image = request.files.get('profile_image')

        if profile_image:
            image_binary = profile_image.read()
            image_base64 = base64.b64encode(image_binary).decode('utf-8')
            user.profile_image = image_base64
            db.session.commit()
            return jsonify(message='プロフィール画像が更新されました。'), 200

    projects = Project.query.filter_by(user_id=user.id).all()

    response_data = {
        "username": user.username,
        "projects": [{
            "id": project.id,
            "name": project.name,
            "created_user":project.user.username,
            "latest_commit_image": project.commits[-1].commit_image,
             "project_star_count": project.star_count,
        } for project in projects],
        "profile_image": user.profile_image,
        "user_id":user.id
    }
    return jsonify(response_data), 200


@app.route('/makeproject', methods=['POST'])
@token_required
def make_project(current_user):
    data = request.form
    project_name = data.get('project_name')
    project_description = data.get('project_description')
    tags = data.get('tags', '').split(',')
    commit_message = data.get('commit_message')
    commit_image = request.files.get('commit_image')

    if commit_image:
        image_binary = commit_image.read()
        image_base64 = base64.b64encode(image_binary).decode('utf-8')
    else:
        return '', 400

    new_project = Project(
        name=project_name,
        description=project_description,
        tags=tags,
        user_id=current_user.id
    )
    new_project.members.append(current_user)
    db.session.add(new_project)
    db.session.commit()

    new_commit = Commit(
        commit_message=commit_message,
        commit_image=image_base64,
        project_id=new_project.id,
        user_id=current_user.id
    )
    db.session.add(new_commit)
    db.session.commit()

    return jsonify(project_id=new_project.id), 201


@app.route('/project/<int:project_id>', methods=['GET', 'PATCH', 'DELETE'])
@token_required
def project_detail(current_user, project_id):
    project = Project.query.get_or_404(project_id)
    star_entry = db.session.execute(stars_table.select().where(stars_table.c.user_id == current_user.id,stars_table.c.project_id == project.id)).fetchone() is not None    
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
                        stars_table.c.user_id == current_user.id,
                        stars_table.c.project_id == project.id
                    )
                )
                project.star_count -= 1
            else:
                db.session.execute(
                    stars_table.insert().values(user_id=current_user.id, project_id=project.id, starred=True)
                )
                project.star_count += 1

            db.session.commit()
            return '', 200

    elif request.method == 'DELETE':
        db.session.delete(project)
        db.session.commit()
        return '', 200

    latest_commit = Commit.query.filter_by(project_id=project.id).order_by(Commit.id.desc()).first()
    project_members_info = [{"user_id": member.id, "username": member.username, "profile_image": member.profile_image} for member in project.members]
    commit_count = len(project.commits)
    return jsonify(
        project_id=project.id,
        name=project.name,
        description=project.description,
        is_public=project.is_public,
        created_at=project.created_at,
        latest_commit_image=latest_commit.commit_image,
        latest_commit_message=latest_commit.commit_message,
        created_username=project.user.username,
        created_user_id=project.user_id,
        created_user_profile_image=project.user.profile_image,
        project_member=project_members_info,
        commit_count=commit_count,
        project_star_count=project.star_count,
        star_entry=star_entry,
        latest_commit_user_id=latest_commit.user.id,
        latest_commit_username=latest_commit.user.username,
        latest_commit_user_profile_image=latest_commit.user.profile_image,
        latest_commit_created_at=latest_commit.created_at,
        latest_commit_id=latest_commit.id
    ), 200


@app.route('/project/<int:project_id>/invite', methods=['GET', 'POST'])
@token_required
def invite_user(current_user, project_id):
    project = Project.query.get_or_404(project_id)
    project_members_info = [{"user_id": member.id, "username": member.username, "profile_image": member.profile_image} for member in project.members]
    search_query = request.args.get('search', '')
    users = []
    
    if search_query:
        users = User.query.filter(User.username.contains(search_query)).all()

    if request.method == 'POST':
        user_id = request.json.get('user_id')
        user_to_invite = User.query.get(user_id)

        if user_to_invite:
            notification = Notification(
                project_id=project.id,
                type="invite",
                to_user_id=user_to_invite.id,
                from_user_id=current_user.id
            )
            db.session.add(notification)
            db.session.commit()
            return jsonify(message=f'{user_to_invite.username}が招待されました。'), 200

        return '', 404

    return jsonify( project_member=project_members_info, users=[{"id": user.id, "username": user.username, "user_image": user.profile_image} for user in users]), 200


@app.route('/project/<int:project_id>/commit', methods=['POST'])
@token_required
def commit(current_user, project_id):
    project = Project.query.get_or_404(project_id)

    commit_message = request.form.get('commit_message')
    commit_image = request.files.get('commit_image')
    
    if commit_image:
        image_binary = commit_image.read()
        image_base64 = base64.b64encode(image_binary).decode('utf-8')
    else:
        return '', 400

    new_commit = Commit(
        commit_message=commit_message,
        commit_image=image_base64,
        project_id=project.id,
        user_id=current_user.id
    )
    db.session.add(new_commit)
    db.session.commit()

    users = project.members
    for member in users:
        if member.id != current_user.id:
            notification = Notification(
                type="commit",
                to_user_id=member.id,
                from_user_id=current_user.id,
                project_id=project.id,
                commit_id=commit.id
            )
            db.session.add(notification)
    db.session.commit()

    return '', 201


@app.route('/project/<int:project_id>/commits')
@token_required
def commits(current_user, project_id):
    project = Project.query.get_or_404(project_id)
    commits = Commit.query.filter_by(project_id=project.id).order_by(Commit.id.desc()).all()

    return jsonify(commits=[{
        "id": commit.id,
        "created_username": commit.user.username,
        "created_user_id": commit.user_id,
        "created_user_profile_image": commit.user.profile_image,
        "commit_message": commit.commit_message,
        "commit_image": commit.commit_image,
        "created_at": commit.created_at
    } for commit in commits]), 200


@app.route('/project/<int:project_id>/commit/<int:commit_id>', methods=['GET', 'POST'])
@token_required
def commit_detail(current_user, project_id, commit_id):
    project = Project.query.get_or_404(project_id)
    commit = Commit.query.get_or_404(commit_id)
    
    if request.method == 'POST':
        data = request.get_json()
        content = data.get('content')
        
        if content:
            comment = CommitComment(content=content, commit_id=commit.id, user_id=current_user.id)
            db.session.add(comment)
            db.session.commit()

            users = project.members
            for member in users:
                if member.id != current_user.id:
                    notification = Notification(
                        type="comment",
                        to_user_id=member.id,
                        from_user_id=current_user.id,
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
            'username': comment.user.username,
            'profile_image': comment.user.profile_image
        }
    } for comment in comments]

    return jsonify(
        project_id=project.id,
        project_name=project.name,
        commit_id=commit.id,
        created_username=commit.user.username,
        created_user_id=commit.user_id,
        created_user_profile_image=commit.user.profile_image,
        commit_message=commit.commit_message,
        commit_image=commit.commit_image,
        created_at=commit.created_at,
        comments=comment_data
    ), 200
#__________________________________通知_________________________________________

@app.route('/notification/<int:notification_id>/respond/<string:response>', methods=['PATCH'])
@token_required
def respond_to_invitation(current_user, notification_id, response):
    data = request.get_json()
    response = data.get('response')
    notification = Notification.query.filter_by(id=notification_id).first_or_404()
    
    if response == 'accept':
        notification.status = 'accepted'
        project = notification.project
        project.members.append(current_user)
        db.session.commit()
        return '', 200
    
    elif response == 'decline':
        notification.status = 'declined'
        db.session.commit()
        return '', 200