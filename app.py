from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import urllib.parse, urllib.request, json
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev_secret')

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXT = {'png','jpg','jpeg','gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Tag categories used for grouping tags on display
TAG_CATEGORIES = {
    'weather': {'sunny', 'rain', 'cloudy', 'cold'},
    'terrain': {'gravel', 'offroad', 'highway', 'city'},
    'style':   {'commute', 'tour', 'sport', 'leisure'}
}

# ======== EVENTS / MEETUPS SYSTEM ========

# Define event categories and status
EVENT_CATEGORIES = {
    'ride': '🏍️ Group Ride',
    'meetup': '☕ Meetup',
    'charity': '❤️ Charity Ride',
    'track_day': '🏁 Track Day',
    'casual': '😎 Casual Hangout',
    'tour': '🗺️ Multi-Day Tour'
}

EVENT_STATUSES = {
    'upcoming': '📅 Upcoming',
    'ongoing': '🔴 Ongoing',
    'past': '⏱️ Past',
    'cancelled': '❌ Cancelled'
}

def query_db(query, args=(), one=False):
    conn = sqlite3.connect('moto_log.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

def categorize_tags(tags_str):
    """
    Accepts a comma-separated tag string and returns:
      - groups: dict with keys 'weather','terrain','style','other' -> lists of tags sorted alphabetically
      - flat: flattened list in the order weather, terrain, style, other
    """
    tags = [t.strip() for t in (tags_str or '').split(',') if t.strip()]
    groups = {'weather': [], 'terrain': [], 'style': [], 'other': []}

    for t in tags:
        low = t.lower()
        placed = False
        for cat, setvals in TAG_CATEGORIES.items():
            if low in setvals:
                groups[cat].append(t)
                placed = True
                break
        if not placed:
            groups['other'].append(t)

    # Sort each group's tags alphabetically (case-insensitive)
    for k in groups:
        groups[k] = sorted(groups[k], key=lambda s: s.lower())

    # Flatten in the desired display order
    flat = groups['weather'] + groups['terrain'] + groups['style'] + groups['other']
    return groups, flat

# Make query_db available in all templates
app.jinja_env.globals.update(query_db=query_db)

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        country = request.form['country']
        hashed_password = generate_password_hash(password)

        try:
            query_db(
                'INSERT INTO users (username, email, password, country) VALUES (?, ?, ?, ?)',
                (username, email, hashed_password, country)
            )
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists. Please log in.', 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)
        if user is None:
            flash("User doesn't exist. Please register first.", 'error')
        elif not check_password_hash(user['password'], password):
            flash('Incorrect password. Please try again.', 'error')
        else:
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['username'] = user['username']
            session['country'] = user['country']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    raw_rides = query_db('SELECT * FROM rides WHERE user_id = ? ORDER BY date DESC', (user_id,))

    rides = []
    for r in raw_rides:
        groups, flat = categorize_tags(r['tags'])
        row = dict(r)
        row['tag_groups'] = groups
        row['tag_list'] = flat
        rides.append(row)

    total_rides = len(raw_rides)
    total_distance = sum(ride['distance'] for ride in raw_rides) if raw_rides else 0
    total_time = sum(ride['time'] for ride in raw_rides) if raw_rides else 0
    avg_distance = total_distance / total_rides if total_rides > 0 else 0

    return render_template('dashboard.html', rides=rides, total_rides=total_rides,
                           total_distance=total_distance, avg_distance=avg_distance,
                           total_time=total_time)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    if request.method == 'POST':
        # allow username change + bio + profile picture
        new_username = request.form.get('username','').strip()
        bio = request.form.get('bio','').strip()

        # check username availability (allow same if unchanged)
        if new_username:
            existing = query_db('SELECT id FROM users WHERE username = ? AND id != ?', (new_username, user_id), one=True)
            if existing:
                flash('Username already taken.', 'error')
                return redirect(url_for('profile'))
            query_db('UPDATE users SET username = ? WHERE id = ?', (new_username, user_id))

        # handle profile picture
        file = request.files.get('profile_pic')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"user_{user_id}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            rel = f"/static/{rel}"
            query_db('UPDATE users SET profile_pic = ? WHERE id = ?', (rel, user_id))

        if bio is not None:
            query_db('UPDATE users SET bio = ? WHERE id = ?', (bio, user_id))

        flash('Profile updated.', 'success')
        return redirect(url_for('profile'))

    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    
    # Stats
    total_rides = query_db('SELECT COUNT(*) as c FROM rides WHERE user_id = ?', (user_id,), one=True)['c']
    total_distance = query_db('SELECT COALESCE(SUM(distance), 0) as d FROM rides WHERE user_id = ?', (user_id,), one=True)['d']
    
    # Followers / Following
    followers = query_db('''
        SELECT u.id, u.username, u.profile_pic 
        FROM users u 
        JOIN follows f ON u.id = f.follower_id 
        WHERE f.followed_id = ? 
        ORDER BY f.created_at DESC
    ''', (user_id,))
    
    following = query_db('''
        SELECT u.id, u.username, u.profile_pic 
        FROM users u 
        JOIN follows f ON u.id = f.followed_id 
        WHERE f.follower_id = ? 
        ORDER BY f.created_at DESC
    ''', (user_id,))

    return render_template('profile.html', user=user, total_rides=total_rides, 
                           total_distance=total_distance, followers=followers, 
                           following=following)

# View other user's public profile
@app.route('/user/<int:user_id>')
def user_profile(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('leaderboard'))
    
    # Stats
    total_rides = query_db('SELECT COUNT(*) as c FROM rides WHERE user_id = ? AND is_private = 0', (user_id,), one=True)['c']
    total_distance = query_db('SELECT COALESCE(SUM(distance), 0) as d FROM rides WHERE user_id = ? AND is_private = 0', (user_id,), one=True)['d']
    
    # Followers / Following
    followers = query_db('''
        SELECT u.id, u.username, u.profile_pic 
        FROM users u 
        JOIN follows f ON u.id = f.follower_id 
        WHERE f.followed_id = ? 
        ORDER BY f.created_at DESC
    ''', (user_id,))
    
    following = query_db('''
        SELECT u.id, u.username, u.profile_pic 
        FROM users u 
        JOIN follows f ON u.id = f.followed_id 
        WHERE f.follower_id = ? 
        ORDER BY f.created_at DESC
    ''', (user_id,))
    
    # Public rides
    raw_rides = query_db('SELECT * FROM rides WHERE user_id = ? AND is_private = 0 ORDER BY date DESC LIMIT 10', (user_id,))
    rides = []
    for r in raw_rides:
        groups, flat = categorize_tags(r['tags'])
        row = dict(r)
        row['tag_groups'] = groups
        row['tag_list'] = flat
        rides.append(row)

    # Check if current user follows this user
    is_following = False
    if 'user_id' in session:
        is_following = query_db('SELECT id FROM follows WHERE follower_id = ? AND followed_id = ?', 
                                (session['user_id'], user_id), one=True) is not None

    return render_template('user_profile.html', user=user, total_rides=total_rides,
                           total_distance=total_distance, followers=followers, 
                           following=following, rides=rides, is_following=is_following)

# Bikes - list/add/edit/delete
@app.route('/bikes')
def bikes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    bikes = query_db('SELECT * FROM bikes WHERE user_id = ?', (user_id,))
    return render_template('bikes.html', bikes=bikes)

@app.route('/add-bike', methods=['GET','POST'])
def add_bike():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = session['user_id']
        name = request.form.get('name','').strip()
        make_model = request.form.get('make_model','').strip()
        year = request.form.get('year') or None
        odo = request.form.get('odo') or 0
        notes = request.form.get('notes','').strip()
        is_private = 1 if request.form.get('is_private') == 'on' else 0
        image_path = None

        # handle bike image upload
        file = request.files.get('bike_image')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"bike_{user_id}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            image_path = f"/static/{rel}"

        if not name:
            flash('Bike name required.', 'error')
        else:
            query_db('INSERT INTO bikes (user_id,name,make_model,year,odo,image,notes,is_private) VALUES (?,?,?,?,?,?,?,?)',
                     (user_id, name, make_model, year, odo, image_path, notes, is_private))
            flash('Bike added.', 'success')
            return redirect(url_for('bikes'))
    return render_template('add_bike.html')

@app.route('/edit-bike/<int:bike_id>', methods=['GET','POST'])
def edit_bike(bike_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    bike = query_db('SELECT * FROM bikes WHERE id = ? AND user_id = ?', (bike_id, session['user_id']), one=True)
    if not bike:
        flash('Bike not found.', 'error'); return redirect(url_for('bikes'))
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        make_model = request.form.get('make_model','').strip()
        year = request.form.get('year') or None
        odo = request.form.get('odo') or 0
        notes = request.form.get('notes','').strip()
        is_private = 1 if request.form.get('is_private') == 'on' else 0

        # handle bike image upload (replace if provided)
        file = request.files.get('bike_image')
        image_path = bike['image']
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"bike_{session['user_id']}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            image_path = f"/static/{rel}"

        query_db('UPDATE bikes SET name=?, make_model=?, year=?, odo=?, image=?, notes=?, is_private=? WHERE id=?',
                 (name, make_model, year, odo, image_path, notes, is_private, bike_id))
        flash('Bike updated.', 'success')
        return redirect(url_for('bikes'))
    return render_template('edit_bike.html', bike=bike)

# View user's public garage
@app.route('/user/<int:user_id>/garage')
def user_garage(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('leaderboard'))
    
    # Get public bikes only
    bikes = query_db('SELECT * FROM bikes WHERE user_id = ? AND is_private = 0 ORDER BY name', (user_id,))
    
    return render_template('user_garage.html', user=user, bikes=bikes)

# -------- Group chat routes --------

@app.route('/groups/create', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name','').strip()
        member_ids = request.form.getlist('members')
        file = request.files.get('group_pic')
        if not name:
            flash('Group name required.', 'error')
            return redirect(url_for('create_group'))

        pic_path = None
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"group_{session['user_id']}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            pic_path = f"/static/{rel}"

        # create group
        query_db('INSERT INTO groups (name, owner_id, profile_pic) VALUES (?, ?, ?)', (name, session['user_id'], pic_path))
        group = query_db('SELECT id FROM groups ORDER BY id DESC LIMIT 1', (), one=True)
        group_id = group['id']

        # add owner as member
        query_db('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, session['user_id']))
        # add other selected members
        for uid in member_ids:
            try:
                uid_int = int(uid)
                if uid_int == session['user_id']:
                    continue
                exists = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, uid_int), one=True)
                if not exists:
                    query_db('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, uid_int))
            except ValueError:
                continue

        flash('Group created.', 'success')
        return redirect(url_for('group_chat', group_id=group_id))

    # GET: show only friends (mutual follows)
    friends = query_db('''
        SELECT DISTINCT u.id, u.username, u.profile_pic
        FROM users u
        WHERE u.id != ? 
        AND EXISTS (SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = u.id)
        AND EXISTS (SELECT 1 FROM follows WHERE follower_id = u.id AND followed_id = ?)
        ORDER BY u.username
    ''', (session['user_id'], session['user_id'], session['user_id']))
    
    return render_template('create_group.html', users=friends)


@app.route('/groups/<int:group_id>')
def group_chat(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # ensure group exists
    group = query_db('SELECT * FROM groups WHERE id = ?', (group_id,), one=True)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('messages'))

    # check membership
    member = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']), one=True)
    if not member:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('messages'))

    # Mark all group messages as read for this user by updating last_read timestamp
    query_db('UPDATE group_members SET last_read = datetime("now") WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']))

    # fetch messages with special handling for system messages (sender_id = 0)
    msgs = query_db('''
        SELECT gm.*, u.username, u.profile_pic FROM group_messages gm
        LEFT JOIN users u ON gm.sender_id = u.id
        WHERE gm.group_id = ?
        ORDER BY gm.created_at ASC
    ''', (group_id,))

    # fetch members
    members = query_db('''
        SELECT u.id, u.username, u.profile_pic FROM users u
        JOIN group_members gm ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.username
    ''', (group_id,))

    return render_template('group_chat.html', group=group, messages=msgs, members=members)


@app.route('/groups/<int:group_id>/send', methods=['POST'])
def send_group_message(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    content = request.form.get('message','').strip()
    if not content:
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('group_chat', group_id=group_id))

    # check membership
    member = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']), one=True)
    if not member:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('messages'))

    query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
             (group_id, session['user_id'], content))
    return redirect(url_for('group_chat', group_id=group_id) + '#bottom')


@app.route('/groups/<int:group_id>/members')
def group_members_view(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    group = query_db('SELECT * FROM groups WHERE id = ?', (group_id,), one=True)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('messages'))

    # ensure requesting user is member (members can view)
    member = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']), one=True)
    if not member:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('messages'))

    members = query_db('''
        SELECT u.id, u.username, u.profile_pic FROM users u
        JOIN group_members gm ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.username
    ''', (group_id,))

    return render_template('group_members.html', group=group, members=members)


@app.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
def group_edit(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    group = query_db('SELECT * FROM groups WHERE id = ?', (group_id,), one=True)
    if not group:
        flash('Group not found.', 'error')
        return redirect(url_for('messages'))

    # membership check: only members can access edit page
    member_row = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']), one=True)
    if not member_row:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('messages'))

    is_owner = (group['owner_id'] == session['user_id'])

    if request.method == 'POST':
        # NAME: any member may change the name
        name = request.form.get('name', '').strip()
        if name and name != (group['name'] or ''):
            query_db('UPDATE groups SET name = ? WHERE id = ?', (name, group_id))
            # log to group messages (sender_id = 0 marks as system message)
            actor = session.get('username') or f'User {session["user_id"]}'
            content = f"{actor} changed the group name to \"{name}\""
            query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                     (group_id, 0, content))

        # PHOTO: any member may change the picture
        file = request.files.get('group_pic')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"group_{group_id}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            pic_path = f"/static/{rel}"
            query_db('UPDATE groups SET profile_pic = ? WHERE id = ?', (pic_path, group_id))
            actor = session.get('username') or f'User {session["user_id"]}'
            content = f"{actor} changed the group photo."
            query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                     (group_id, 0, content))

        # ANY MEMBER: add members (only mutual friends of the current user)
        add_ids = request.form.getlist('add_members')
        for uid in add_ids:
            try:
                uid_int = int(uid)
            except ValueError:
                continue

            # skip if already member or adding self
            if uid_int == session['user_id']:
                continue
            exists = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, uid_int), one=True)
            if exists:
                continue

            # mutual friendship check: current user follows uid AND uid follows current user
            a = query_db('SELECT id FROM follows WHERE follower_id = ? AND followed_id = ?', (session['user_id'], uid_int), one=True)
            b = query_db('SELECT id FROM follows WHERE follower_id = ? AND followed_id = ?', (uid_int, session['user_id']), one=True)
            if a and b:
                query_db('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, uid_int))
                added_user = query_db('SELECT username FROM users WHERE id = ?', (uid_int,), one=True)
                actor = session.get('username') or f'User {session["user_id"]}'
                added_name = added_user['username'] if added_user else f'User {uid_int}'
                content = f"{actor} added {added_name} to the group."
                query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                         (group_id, 0, content))
            else:
                flash(f'Cannot add user {uid_int}: not a mutual friend.', 'error')

        # OWNER-only: remove member
        remove_id = request.form.get('remove_member')
        if remove_id:
            try:
                rid = int(remove_id)
            except ValueError:
                rid = None
            if rid:
                if not is_owner:
                    flash('Only the owner can remove members.', 'error')
                else:
                    if rid == group['owner_id']:
                        flash("Cannot remove the owner.", 'error')
                    else:
                        # get username for logging
                        removed_user = query_db('SELECT username FROM users WHERE id = ?', (rid,), one=True)
                        removed_name = removed_user['username'] if removed_user else f'User {rid}'
                        query_db('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, rid))
                        actor = session.get('username') or f'User {session["user_id"]}'
                        content = f"{actor} removed {removed_name} from the group."
                        query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                                 (group_id, 0, content))

        flash('Group updated.', 'success')
        return redirect(url_for('group_edit', group_id=group_id))

    # GET: compute current members
    members = query_db('SELECT u.id, u.username, u.profile_pic FROM users u JOIN group_members gm ON u.id = gm.user_id WHERE gm.group_id = ? ORDER BY u.username', (group_id,))

    # compute addable friends for the current user: mutual followers who are NOT already members
    current_member_rows = query_db('SELECT user_id FROM group_members WHERE group_id = ?', (group_id,))
    current_ids = set([r['user_id'] for r in current_member_rows]) if current_member_rows else set()

    friends = query_db('''
        SELECT DISTINCT u.id, u.username, u.profile_pic
        FROM users u
        WHERE u.id != ?
          AND EXISTS (SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = u.id)
          AND EXISTS (SELECT 1 FROM follows WHERE follower_id = u.id AND followed_id = ?)
        ORDER BY u.username
    ''', (session['user_id'], session['user_id'], session['user_id']))

    add_available_friends = [f for f in friends if f['id'] not in current_ids]

    # owner info for template
    owner = query_db('SELECT id, username FROM users WHERE id = ?', (group['owner_id'],), one=True)
    return render_template('group_edit.html', group=group, add_available_friends=add_available_friends, members=members, owner=owner)


# Messages routes
@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    # user-to-user conversations (existing)
    conversations = query_db('''
        SELECT DISTINCT 
            CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END as other_user_id,
            MAX(created_at) as last_msg_time
        FROM messages
        WHERE sender_id = ? OR recipient_id = ?
        GROUP BY other_user_id
        ORDER BY last_msg_time DESC
    ''', (uid, uid, uid))

    # Enrich with user info
    conv_list = []
    for conv in conversations:
        other_id = conv['other_user_id']
        other_user = query_db('SELECT id, username, profile_pic FROM users WHERE id = ?', (other_id,), one=True)
        # Only count messages FROM the other user TO you that are unread
        unread = query_db('SELECT COUNT(*) as c FROM messages WHERE sender_id = ? AND recipient_id = ? AND is_read = 0', 
                         (other_id, uid), one=True)['c']
        conv_list.append({
            'type': 'user',
            'user': other_user,
            'unread': unread,
            'last_time': conv['last_msg_time']
        })

    # group conversations: groups user is member of + last message time
    groups = query_db('''
        SELECT g.id, g.name, g.profile_pic, MAX(gm.created_at) AS last_msg_time
        FROM groups g
        JOIN group_members gmbr ON g.id = gmbr.group_id
        LEFT JOIN group_messages gm ON g.id = gm.group_id
        WHERE gmbr.user_id = ?
        GROUP BY g.id
        ORDER BY last_msg_time DESC
    ''', (uid,))

    group_list = []
    for g in groups:
        # Count unread: messages created AFTER user's last_read time, excluding system messages (sender_id != 0) and excluding messages sent by current user
        last_read = query_db('SELECT last_read FROM group_members WHERE group_id = ? AND user_id = ?', (g['id'], uid), one=True)
        last_read_time = last_read['last_read'] if last_read and last_read['last_read'] else '1900-01-01'
        unread = query_db('SELECT COUNT(*) as c FROM group_messages WHERE group_id = ? AND sender_id != 0 AND sender_id != ? AND created_at > ?', 
                          (g['id'], uid, last_read_time), one=True)['c']
        group_list.append({
            'type': 'group',
            'group': g,
            'unread': unread,
            'last_time': g['last_msg_time']
        })

    # Combine both conversation types with type indicator
    all_convs = []
    for conv in conv_list:
        all_convs.append({
            'type': 'user',
            'unread': conv['unread'],
            'last_time': conv['last_time'],
            'id': conv['user']['id'],
            'name': conv['user']['username'],
            'profile_pic': conv['user']['profile_pic'],
        })
    
    for g in group_list:
        all_convs.append({
            'type': 'group',
            'unread': g['unread'],
            'last_time': g['last_time'],
            'id': g['group']['id'],
            'name': g['group']['name'],
            'profile_pic': g['group']['profile_pic'],
        })
    
    # Sort by most recent time (descending)
    def sort_key(c):
        time_str = c['last_time'] or '1900-01-01'
        return time_str
    
    all_convs.sort(key=sort_key, reverse=True)

    return render_template('messages.html', conversations=all_convs)

@app.route('/messages/with/<int:user_id>')
def chat_with(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_uid = session['user_id']
    other_user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not other_user:
        flash('User not found.', 'error')
        return redirect(url_for('messages'))
    
    # Get all messages between these two users
    msgs = query_db('''
        SELECT m.*, u.username, u.profile_pic FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.recipient_id = ?) OR (m.sender_id = ? AND m.recipient_id = ?)
        ORDER BY m.created_at ASC
    ''', (current_uid, user_id, user_id, current_uid))
    
    # Mark messages as read
    query_db('UPDATE messages SET is_read = 1 WHERE sender_id = ? AND recipient_id = ?', (user_id, current_uid))
    
    return render_template('chat.html', other_user=other_user, messages=msgs)

@app.route('/messages/send/<int:recipient_id>', methods=['POST'])
def send_message_to(recipient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form.get('message', '').strip()
    if content:
        query_db('INSERT INTO messages (sender_id, recipient_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                 (session['user_id'], recipient_id, content))
        flash('Message sent.', 'success')
    
    return redirect(url_for('chat_with', user_id=recipient_id))

# AJAX: Send group message
@app.route('/groups/<int:group_id>/send-ajax', methods=['POST'])
def send_group_message_ajax(group_id):
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401

    data = request.get_json()
    content = data.get('message', '').strip()
    
    if not content:
        return {'success': False, 'error': 'Empty message'}, 400

    # check membership
    member = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, session['user_id']), one=True)
    if not member:
        return {'success': False, 'error': 'Not a member'}, 403

    query_db('INSERT INTO group_messages (group_id, sender_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
             (group_id, session['user_id'], content))
    return {'success': True}

# AJAX: Get group messages
@app.route('/groups/<int:group_id>/messages-ajax')
def get_group_messages_ajax(group_id):
    if 'user_id' not in session:
        return {'messages': []}, 401

    current_uid = session['user_id']
    
    # check membership
    member = query_db('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, current_uid), one=True)
    if not member:
        return {'messages': []}, 403

    # Update last_read to now to mark all previous messages as read
    query_db('UPDATE group_members SET last_read = datetime("now") WHERE group_id = ? AND user_id = ?', (group_id, current_uid))

    msgs = query_db('''
        SELECT gm.*, u.username, u.profile_pic FROM group_messages gm
        LEFT JOIN users u ON gm.sender_id = u.id
        WHERE gm.group_id = ?
        ORDER BY gm.created_at ASC
    ''', (group_id,))

    messages = []
    for msg in msgs:
        messages.append({
            'id': msg['id'],
            'sender_id': msg['sender_id'],
            'username': msg['username'],
            'content': msg['content'],
            'created_at': msg['created_at']
        })
    
    return {'messages': messages}

# AJAX: Send user message
@app.route('/messages/send-ajax/<int:recipient_id>', methods=['POST'])
def send_message_ajax(recipient_id):
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401

    data = request.get_json()
    content = data.get('message', '').strip()
    
    if not content:
        return {'success': False, 'error': 'Empty message'}, 400

    query_db('INSERT INTO messages (sender_id, recipient_id, content, is_read, created_at) VALUES (?, ?, ?, 1, datetime("now"))',
             (session['user_id'], recipient_id, content))
    return {'success': True}

# AJAX: Poll user messages
@app.route('/messages/poll/<int:other_user_id>')
def poll_messages(other_user_id):
    if 'user_id' not in session:
        return {'messages': []}, 401

    current_uid = session['user_id']
    
    # Mark messages as read
    query_db('UPDATE messages SET is_read = 1 WHERE sender_id = ? AND recipient_id = ?', (other_user_id, current_uid))

    msgs = query_db('''
        SELECT m.*, u.username, u.profile_pic FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.recipient_id = ?) OR (m.sender_id = ? AND m.recipient_id = ?)
        ORDER BY m.created_at ASC
    ''', (current_uid, other_user_id, other_user_id, current_uid))

    messages = []
    for msg in msgs:
        messages.append({
            'id': msg['id'],
            'sender_id': msg['sender_id'],
            'username': msg['username'],
            'content': msg['content'],
            'created_at': msg['created_at']
        })
    
    return {'messages': messages}

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/tools', methods=['GET', 'POST'])
def tools():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    # Handle weather request (form POST with city)
    weather_data = None
    if request.method == 'POST' and request.form.get('action') == 'weather':
        city = request.form.get('city', '').strip()
        api_key = os.environ.get('OPENWEATHER_API_KEY')
        if not api_key:
            flash('OpenWeather API key not set (OPENWEATHER_API_KEY). Weather unavailable.', 'error')
        elif not city:
            flash('Please provide a city for weather lookup.', 'error')
        else:
            try:
                q = urllib.parse.quote(city)
                url = f'https://api.openweathermap.org/data/2.5/weather?q={q}&units=metric&appid={api_key}'
                with urllib.request.urlopen(url, timeout=6) as resp:
                    w = json.load(resp)
                    weather_data = {
                        'city': w.get('name'),
                        'temp': w['main']['temp'],
                        'desc': w['weather'][0]['description'],
                        'wind': w['wind']['speed']
                    }
            except Exception as e:
                flash('Weather lookup failed: ' + str(e), 'error')

    # Handle emergency info update
    if request.method == 'POST' and request.form.get('action') == 'emergency':
        name = request.form.get('em_name', '').strip()
        phone = request.form.get('em_phone', '').strip()
        query_db('UPDATE users SET emergency_name = ?, emergency_phone = ? WHERE id = ?', (name, phone, user_id))
        flash('Emergency info updated.', 'success')

    # Maintenance CRUD - add
    if request.method == 'POST' and request.form.get('action') == 'add_maintenance':
        item = request.form.get('item', '').strip()
        due = request.form.get('due_date', '').strip()
        last = request.form.get('last_changed', '').strip()
        notes = request.form.get('notes', '').strip()
        if not item:
            flash('Maintenance item is required.', 'error')
        else:
            query_db('INSERT INTO maintenance (user_id, item, due_date, last_changed, notes) VALUES (?, ?, ?, ?, ?)',
                     (user_id, item, due or None, last or None, notes))
            flash('Maintenance reminder added.', 'success')
        return redirect(url_for('tools'))

    # Handle delete maintenance via query param
    delete_id = request.args.get('delete_maint')
    if delete_id:
        query_db('DELETE FROM maintenance WHERE id = ? AND user_id = ?', (delete_id, user_id))
        flash('Maintenance reminder deleted.', 'success')
        return redirect(url_for('tools'))

    maint = query_db('SELECT * FROM maintenance WHERE user_id = ? ORDER BY due_date IS NULL, due_date', (user_id,))
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)

    return render_template('tools.html', maintenance=maint, user=user, weather=weather_data)

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = query_db('SELECT * FROM users WHERE id = ?', (session['user_id'],), one=True)
    user_country = user['country'] if user else 'Unknown'
    global_leaderboard = query_db('''
        SELECT u.id, u.username, u.country, u.profile_pic,
               COALESCE(SUM(r.distance), 0) AS total_distance
        FROM users u
        LEFT JOIN rides r ON r.user_id = u.id
        GROUP BY u.id
        ORDER BY total_distance DESC
        LIMIT 50
    ''')
    local_leaderboard = query_db('''
        SELECT u.id, u.username, u.country, u.profile_pic,
               COALESCE(SUM(r.distance), 0) AS total_distance
        FROM users u
        LEFT JOIN rides r ON r.user_id = u.id
        WHERE u.country = ?
        GROUP BY u.id
        ORDER BY total_distance DESC
        LIMIT 50
    ''', (user_country,))
    return render_template('leaderboard.html',
                           global_leaderboard=global_leaderboard,
                           local_leaderboard=local_leaderboard,
                           user_country=user_country)

@app.route('/edit-ride/<int:ride_id>', methods=['GET', 'POST'])
def edit_ride(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    ride = query_db('SELECT * FROM rides WHERE id = ? AND user_id = ?', (ride_id, user_id), one=True)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(url_for('dashboard'))

    bikes = query_db('SELECT * FROM bikes WHERE user_id = ?', (user_id,))

    if request.method == 'POST':
        bike_id = request.form.get('bike_id') or None
        date = request.form.get('date', ride['date'])
        distance = float(request.form.get('distance', ride['distance'] or 0))
        time_val = float(request.form.get('time', ride['time'] or 0))
        description = request.form.get('description','').strip()
        tags_list = request.form.getlist('tag') or []
        custom = request.form.get('custom_tags','').strip()
        if custom:
            tags_list += [t.strip() for t in custom.split(',') if t.strip()]
        
        # Sort tags alphabetically (case-insensitive) for consistency
        tags_list = [t.strip() for t in tags_list if t.strip()]
        tags_list = sorted(dict.fromkeys(tags_list), key=lambda s: s.lower())  # keep order deterministic and remove duplicates
        tags = ','.join(tags_list) if tags_list else None
        
        is_private = 1 if request.form.get('is_private') == 'on' else 0

        query_db('''
            UPDATE rides SET bike_id = ?, date = ?, distance = ?, time = ?, description = ?, tags = ?, is_private = ?
            WHERE id = ? AND user_id = ?
        ''', (bike_id, date, distance, time_val, description, tags, is_private, ride_id, user_id))

        flash('Ride updated.', 'success')
        return redirect(url_for('dashboard'))

    # prepare pre-checked tags for template convenience
    existing_tags = (ride['tags'] or '').split(',') if ride['tags'] else []
    return render_template('edit_ride.html', ride=ride, bikes=bikes, existing_tags=existing_tags)

# Add comment to a ride
@app.route('/ride/<int:ride_id>/comment', methods=['POST'])
def add_comment(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = request.form.get('comment', '').strip()
    if not content:
        flash('Comment cannot be empty.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # Ensure ride exists and is commentable
    ride = query_db('SELECT * FROM rides WHERE id = ?', (ride_id,), one=True)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # Prevent commenting on private rides you don't own
    # sqlite3.Row uses mapping access, use indexing rather than .get()
    is_private = ride['is_private'] if 'is_private' in ride.keys() else 0
    owner_id = ride['user_id']
    if is_private and session['user_id'] != owner_id:
        flash('Cannot comment on a private ride.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    try:
        query_db('INSERT INTO comments (ride_id, user_id, content, created_at) VALUES (?, ?, ?, datetime("now"))',
                 (ride_id, session['user_id'], content))
        flash('Comment posted.', 'success')
    except Exception as e:
        flash('Failed to post comment: ' + str(e), 'error')

    # Redirect back to the page where the form was submitted
    return redirect(request.referrer or url_for('user_profile', user_id=owner_id))


# Toggle like on a ride
@app.route('/ride/<int:ride_id>/like', methods=['POST'])
def like_ride(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    ride = query_db('SELECT * FROM rides WHERE id = ?', (ride_id,), one=True)
    if not ride:
        flash('Ride not found.', 'error')
        return redirect(request.referrer or url_for('dashboard'))

    try:
        existing = query_db('SELECT id FROM likes WHERE user_id = ? AND ride_id = ?', (uid, ride_id), one=True)
        if existing:
            query_db('DELETE FROM likes WHERE id = ?', (existing['id'],))
            flash('Removed like.', 'success')
        else:
            query_db('INSERT INTO likes (user_id, ride_id, created_at) VALUES (?, ?, datetime("now"))', (uid, ride_id))
            flash('Liked!', 'success')
    except Exception as e:
        flash('Failed to update like: ' + str(e), 'error')

    return redirect(request.referrer or url_for('user_profile', user_id=ride['user_id']))


# Bike maintenance view for a specific bike
@app.route('/bike/<int:bike_id>/maintenance', methods=['GET', 'POST'])
def bike_maintenance_view(bike_id):
    bike = query_db('SELECT * FROM bikes WHERE id = ?', (bike_id,), one=True)
    if not bike:
        flash('Bike not found.', 'error')
        return redirect(url_for('bikes') if 'user_id' in session else url_for('leaderboard'))

    # Permission: if bike is private and viewer is not owner, deny access
    try:
        is_private = int(bike['is_private']) if 'is_private' in bike.keys() else 0
    except Exception:
        is_private = 0

    if is_private and ('user_id' not in session or session['user_id'] != bike['user_id']):
        flash('This bike is private.', 'error')
        return redirect(url_for('user_garage', user_id=bike['user_id']))

    owner = query_db('SELECT id, username, profile_pic FROM users WHERE id = ?', (bike['user_id'],), one=True)

    # Handle add / delete via POST
    if request.method == 'POST':
        if 'add_maintenance' in request.form:
            # only owner can add
            if 'user_id' not in session or session['user_id'] != bike['user_id']:
                flash('Only the bike owner can add maintenance entries.', 'error')
                return redirect(request.referrer or url_for('bike_maintenance_view', bike_id=bike_id))

            item = request.form.get('item', '').strip()
            date = request.form.get('date', '').strip() or None
            notes = request.form.get('notes', '').strip()
            if not item:
                flash('Maintenance item required.', 'error')
            else:
                query_db('INSERT INTO bike_maintenance (bike_id, item, date, notes) VALUES (?, ?, ?, ?)',
                         (bike_id, item, date, notes))
                flash('Maintenance entry added.', 'success')
            return redirect(url_for('bike_maintenance_view', bike_id=bike_id))

        if 'delete_entry' in request.form:
            # only owner can delete
            if 'user_id' not in session or session['user_id'] != bike['user_id']:
                flash('Only the bike owner can remove maintenance entries.', 'error')
                return redirect(request.referrer or url_for('bike_maintenance_view', bike_id=bike_id))
            entry_id = request.form.get('entry_id')
            if entry_id:
                query_db('DELETE FROM bike_maintenance WHERE id = ? AND bike_id = ?', (entry_id, bike_id))
                flash('Maintenance entry removed.', 'success')
            return redirect(url_for('bike_maintenance_view', bike_id=bike_id))

    # GET: show entries
    entries = query_db('SELECT * FROM bike_maintenance WHERE bike_id = ? ORDER BY date DESC', (bike_id,))
    return render_template('bike_maintenance.html', bike=bike, entries=entries, owner=owner)


# Followers / Following listing pages (tabs above)
@app.route('/user/<int:user_id>/followers')
def user_followers(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('leaderboard'))

    followers = query_db('''
        SELECT u.id, u.username, u.profile_pic
        FROM users u
        JOIN follows f ON u.id = f.follower_id
        WHERE f.followed_id = ?
        ORDER BY f.created_at DESC
    ''', (user_id,))

    following = query_db('''
        SELECT u.id, u.username, u.profile_pic
        FROM users u
        JOIN follows f ON u.id = f.followed_id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
    ''', (user_id,))

    return render_template('user_connections.html', user=user, active_tab='followers', followers=followers, following=following)


@app.route('/user/<int:user_id>/following')
def user_following(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('leaderboard'))

    followers = query_db('''
        SELECT u.id, u.username, u.profile_pic
        FROM users u
        JOIN follows f ON u.id = f.follower_id
        WHERE f.followed_id = ?
        ORDER BY f.created_at DESC
    ''', (user_id,))

    following = query_db('''
        SELECT u.id, u.username, u.profile_pic
        FROM users u
        JOIN follows f ON u.id = f.followed_id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
    ''', (user_id,))

    return render_template('user_connections.html', user=user, active_tab='following', followers=followers, following=following)

@app.route('/follow/<int:target_id>', methods=['GET', 'POST'])
def follow_toggle(target_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    if uid == target_id:
        flash("Can't follow yourself.", 'error')
        return redirect(request.referrer or url_for('leaderboard'))

    existing = query_db('SELECT id FROM follows WHERE follower_id=? AND followed_id=?', (uid, target_id), one=True)
    if existing:
        query_db('DELETE FROM follows WHERE id = ?', (existing['id'],))
        flash('Unfollowed user.', 'success')
    else:
        query_db('INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, datetime("now"))', (uid, target_id))
        flash('Now following user.', 'success')

    # If route was called by a POST form, return to referrer; if used by GET link, go to the target profile
    return redirect(request.referrer or url_for('user_profile', user_id=target_id))

@app.route('/profile/edit', methods=['GET', 'POST'])
def profile_edit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    
    if request.method == 'POST':
        # allow username change + bio + profile picture
        new_username = request.form.get('username','').strip()
        bio = request.form.get('bio','').strip()

        # check username availability (allow same if unchanged)
        if new_username:
            existing = query_db('SELECT id FROM users WHERE username = ? AND id != ?', (new_username, user_id), one=True)
            if existing:
                flash('Username already taken.', 'error')
                return redirect(url_for('profile_edit'))
            query_db('UPDATE users SET username = ? WHERE id = ?', (new_username, user_id))
            session['username'] = new_username

        # handle profile picture
        file = request.files.get('profile_pic')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"user_{user_id}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\','/')
            rel = f"/static/{rel}"
            query_db('UPDATE users SET profile_pic = ? WHERE id = ?', (rel, user_id))

        if bio is not None:
            query_db('UPDATE users SET bio = ? WHERE id = ?', (bio, user_id))

        flash('Profile updated.', 'success')
        return redirect(url_for('profile'))

    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    return render_template('edit_profile.html', user=user)

# AJAX: Get total unread count
@app.route('/messages/unread-count')
def unread_count():
    if 'user_id' not in session:
        return {'unread_count': 0}, 401
    
    uid = session['user_id']
    
    # Count unread user messages FROM others TO you (exclude messages you sent)
    user_unread = query_db('SELECT COUNT(*) as c FROM messages WHERE recipient_id = ? AND is_read = 0 AND sender_id != ?', (uid, uid), one=True)['c']
    
    # Count unread group messages FROM others (exclude system messages and messages you sent)
    groups = query_db('SELECT g.id FROM groups g JOIN group_members gm ON g.id = gm.group_id WHERE gm.user_id = ?', (uid,))
    group_unread = 0
    for g in groups:
        last_read = query_db('SELECT last_read FROM group_members WHERE group_id = ? AND user_id = ?', (g['id'], uid), one=True)
        last_read_time = last_read['last_read'] if last_read and last_read['last_read'] else '1900-01-01'
        # Exclude system messages (sender_id != 0) and exclude messages sent by current user (sender_id != uid)
        count = query_db('SELECT COUNT(*) as c FROM group_messages WHERE group_id = ? AND sender_id != 0 AND sender_id != ? AND created_at > ?', 
                        (g['id'], uid, last_read_time), one=True)['c']
        group_unread += count
    
    return {'unread_count': user_unread + group_unread}

# Add ride (GET shows form, POST creates record)
@app.route('/add-ride', methods=['GET', 'POST'])
def add_ride():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    # Provide user's bikes for the select box
    bikes = query_db('SELECT * FROM bikes WHERE user_id = ?', (user_id,))

    if request.method == 'POST':
        bike_id = request.form.get('bike_id') or None
        date = request.form.get('date', '').strip() or None
        try:
            distance = float(request.form.get('distance', 0) or 0)
        except ValueError:
            distance = 0.0
        try:
            time_val = float(request.form.get('time', 0) or 0)
        except ValueError:
            time_val = 0.0

        description = request.form.get('description', '').strip() or None
        tags_list = request.form.getlist('tag') or []
        custom = request.form.get('custom_tags', '').strip()
        if custom:
            tags_list += [t.strip() for t in custom.split(',') if t.strip()]
        
        # Sort tags alphabetically (case-insensitive) for consistency
        tags_list = [t.strip() for t in tags_list if t.strip()]
        tags_list = sorted(dict.fromkeys(tags_list), key=lambda s: s.lower())  # keep order deterministic and remove duplicates
        tags = ','.join(tags_list) if tags_list else None
        
        is_private = 1 if request.form.get('is_private') == 'on' else 0

        try:
            # NOTE: no created_at column in your schema, so do not insert it
            query_db('''
                INSERT INTO rides
                (user_id, bike_id, date, distance, time, description, tags, is_private)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, bike_id, date, distance, time_val, description, tags, is_private))
            flash('Ride saved.', 'success')
        except Exception as e:
            flash('Failed to save ride: ' + str(e), 'error')

        return redirect(url_for('dashboard'))

    # GET -> show add ride form
    return render_template('add_ride.html', bikes=bikes)

# Delete a ride (owner-only). Template currently links to /delete-ride/<id>
@app.route('/delete-ride/<int:ride_id>')
def delete_ride(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    # Ensure the ride exists and belongs to the current user
    ride = query_db('SELECT * FROM rides WHERE id = ? AND user_id = ?', (ride_id, uid), one=True)
    if not ride:
        flash('Ride not found or permission denied.', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Remove dependent rows first (comments, likes) to avoid FK issues / orphaned rows
        query_db('DELETE FROM likes WHERE ride_id = ?', (ride_id,))
        query_db('DELETE FROM comments WHERE ride_id = ?', (ride_id,))
        # Delete the ride itself
        query_db('DELETE FROM rides WHERE id = ? AND user_id = ?', (ride_id, uid))
        flash('Ride deleted.', 'success')
    except Exception as e:
        flash('Failed to delete ride: ' + str(e), 'error')

    return redirect(url_for('dashboard'))

# AJAX / simple GET: search users by username substring
@app.route('/search/users')
def search_users():
    q = (request.args.get('q') or '').strip()
    if not q:
        return {'users': []}
    pattern = f"%{q}%"
    rows = query_db('SELECT id, username, profile_pic FROM users WHERE username LIKE ? COLLATE NOCASE LIMIT 30', (pattern,))
    users = [{'id': r['id'], 'username': r['username'], 'profile_pic': r['profile_pic']} for r in rows]
    return {'users': users}

@app.route('/profile/delete', methods=['POST'])
def delete_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']

    try:
        # Delete likes and comments by user
        query_db('DELETE FROM likes WHERE user_id = ?', (uid,))
        query_db('DELETE FROM comments WHERE user_id = ?', (uid,))

        # Remove follow relationships (both follower and followed)
        query_db('DELETE FROM follows WHERE follower_id = ? OR followed_id = ?', (uid, uid))

        # Delete user messages (sent or received)
        query_db('DELETE FROM messages WHERE sender_id = ? OR recipient_id = ?', (uid, uid))

        # Delete group messages sent by user
        query_db('DELETE FROM group_messages WHERE sender_id = ?', (uid,))

        # Remove from group_members and delete groups owned by the user
        # First, find groups owned by the user and delete them and their data
        owned_groups = query_db('SELECT id FROM groups WHERE owner_id = ?', (uid,))
        for g in owned_groups:
            gid = g['id']
            query_db('DELETE FROM group_messages WHERE group_id = ?', (gid,))
            query_db('DELETE FROM group_members WHERE group_id = ?', (gid,))
            query_db('DELETE FROM groups WHERE id = ?', (gid,))

        # Remove any remaining group memberships for this user
        query_db('DELETE FROM group_members WHERE user_id = ?', (uid,))

        # Delete rides (and their likes/comments)
        # comments/likes for rides created by this user already deleted above per user_id,
        # but remove ride rows themselves:
        query_db('DELETE FROM rides WHERE user_id = ?', (uid,))

        # Finally delete the user row
        query_db('DELETE FROM users WHERE id = ?', (uid,))

        # Clear session and log out
        session.clear()
        flash('Your account has been deleted. Goodbye.', 'success')
        return redirect(url_for('register'))
    except Exception as e:
        # Something failed; don't clear session if deletion didn't complete
        flash('Failed to delete account: ' + str(e), 'error')
        return redirect(url_for('profile'))

# ======== EVENTS / MEETUPS SYSTEM ========

def get_event_status(event_date_str):
    """
    Determine event status based on event date.
    Returns: 'upcoming', 'ongoing', or 'past'
    """
    from datetime import datetime, timedelta
    try:
        event_dt = datetime.fromisoformat(event_date_str)
        now = datetime.now()
        
        # Event is ongoing within 3 hours before and after start
        if event_dt - timedelta(hours=3) <= now <= event_dt + timedelta(hours=3):
            return 'ongoing'
        elif now > event_dt + timedelta(hours=3):
            return 'past'
        else:
            return 'upcoming'
    except:
        return 'upcoming'

@app.route('/events')
def events_browse():
    """Browse all events with filtering and search"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get filter parameters
    category = request.args.get('category', '')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'soonest')  # soonest, popular, nearest
    
    # Base query: only upcoming and ongoing events (exclude cancelled and past)
    query = '''
        SELECT e.*, u.username, u.profile_pic,
               COUNT(DISTINCT ep.user_id) as participant_count
        FROM events e
        JOIN users u ON e.creator_id = u.id
        LEFT JOIN event_participants ep ON e.id = ep.event_id
        WHERE e.status IN ('upcoming', 'ongoing')
    '''
    args = []
    
    # Filter by category
    if category and category in EVENT_CATEGORIES:
        query += ' AND e.category = ?'
        args.append(category)
    
    # Search by title or description
    if search:
        query += ' AND (e.title LIKE ? OR e.description LIKE ?)'
        search_pattern = f'%{search}%'
        args.extend([search_pattern, search_pattern])
    
    query += ' GROUP BY e.id'
    
    # Sorting
    if sort_by == 'popular':
        query += ' ORDER BY participant_count DESC, e.event_date ASC'
    elif sort_by == 'nearest':
        # Nearest requires user location; for now, sort by soonest
        query += ' ORDER BY e.event_date ASC'
    else:  # 'soonest' default
        query += ' ORDER BY e.event_date ASC'
    
    events_rows = query_db(query, args)
    
    # Convert each sqlite3.Row to a mutable dict and enrich with computed fields
    events = []
    current_uid = session['user_id']
    for er in events_rows:
        event = dict(er)  # make a mutable dict
        # Ensure numeric participant_count
        try:
            event['participant_count'] = int(event.get('participant_count') or 0)
        except Exception:
            event['participant_count'] = 0

        is_participant = query_db(
            'SELECT id FROM event_participants WHERE event_id = ? AND user_id = ?',
            (event['id'], current_uid),
            one=True
        ) is not None

        event['is_participant'] = is_participant
        event['can_join'] = (
            event.get('status') in ('upcoming', 'ongoing') and
            not is_participant and
            (event.get('max_participants') is None or event['participant_count'] < (event.get('max_participants') or 0))
        )
        event['status_label'] = EVENT_STATUSES.get(event.get('status'), event.get('status'))
        event['category_label'] = EVENT_CATEGORIES.get(event.get('category'), event.get('category'))
        events.append(event)

    return render_template('events_browse.html',
                           events=events,
                           categories=EVENT_CATEGORIES,
                           current_filter=category,
                           search_query=search,
                           sort_by=sort_by)

@app.route('/events/create', methods=['GET', 'POST'])
def create_event():
    """Create a new event"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        location_name = request.form.get('location_name', '').strip()
        city = request.form.get('city', '').strip()  # NEW: city field
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        category = request.form.get('category', '').strip()
        max_participants = request.form.get('max_participants', '').strip()
        is_local = request.form.get('is_local', 'on') == 'on'
        
        # Validation
        errors = []
        if not title or len(title) < 3:
            errors.append('Title must be at least 3 characters.')
        if not description or len(description) < 10:
            errors.append('Description must be at least 10 characters.')
        if not event_date:
            errors.append('Event date/time is required.')
        if not location_name or len(location_name) < 3:
            errors.append('Location name is required.')
        if not city or len(city) < 2:
            errors.append('City is required.')
        
        # Coordinates are now optional
        lat = None
        lon = None
        if latitude or longitude:
            try:
                lat = float(latitude)
                lon = float(longitude)
                if lat < -90 or lat > 90 or lon < -180 or lon > 180:
                    errors.append('Invalid coordinates. Latitude: -90 to 90, Longitude: -180 to 180.')
            except ValueError:
                errors.append('Coordinates must be valid numbers if provided.')
        
        if category not in EVENT_CATEGORIES:
            errors.append('Invalid event category.')
        
        max_part = None
        if max_participants:
            try:
                max_part = int(max_participants)
                if max_part <= 0:
                    errors.append('Max participants must be positive.')
            except ValueError:
                errors.append('Max participants must be a number.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('create_event'))
        
        # Handle cover image upload
        cover_image = None
        file = request.files.get('cover_image')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"event_{session['user_id']}_{int(datetime.now().timestamp())}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\', '/')
            cover_image = f"/static/{rel}"
        
        now = datetime.now().isoformat()
        query_db('''
            INSERT INTO events
            (creator_id, title, description, event_date, location_name, city, latitude, longitude, category, max_participants, cover_image, is_local, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            title, description, event_date, location_name, city,
            lat, lon, category, max_part, cover_image,
            1 if is_local else 0, 'upcoming', now, now
        ))
        
        flash('Event created successfully!', 'success')
        return redirect(url_for('events_browse'))
    
    return render_template('events_create.html', categories=EVENT_CATEGORIES)

@app.route('/events/<int:event_id>')
def event_detail(event_id):
    """View detailed event information"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event_row = query_db('''
        SELECT e.*, u.id as creator_id, u.username as creator_username, u.profile_pic as creator_pic,
               COUNT(DISTINCT ep.user_id) as participant_count
        FROM events e
        JOIN users u ON e.creator_id = u.id
        LEFT JOIN event_participants ep ON e.id = ep.event_id
        WHERE e.id = ?
        GROUP BY e.id
    ''', (event_id,), one=True)
    
    if not event_row:
        flash('Event not found.', 'error')
        return redirect(url_for('events_browse'))

    # Convert to mutable dict
    event = dict(event_row)

    # Get participants with profile info
    participants = query_db('''
        SELECT u.id, u.username, u.profile_pic
        FROM users u
        JOIN event_participants ep ON u.id = ep.user_id
        WHERE ep.event_id = ?
        ORDER BY ep.joined_at ASC
    ''', (event_id,))
    
    current_uid = session['user_id']
    is_participant = query_db(
        'SELECT id FROM event_participants WHERE event_id = ? AND user_id = ?',
        (event_id, current_uid),
        one=True
    ) is not None
    
    is_creator = (event['creator_id'] == current_uid)
    
    # Determine if user can join
    can_join = (
        not is_creator and
        not is_participant and
        event['status'] in ('upcoming', 'ongoing') and
        (event['max_participants'] is None or event['participant_count'] < event['max_participants'])
    )
    
    can_leave = (
        not is_creator and
        is_participant and
        event['status'] in ('upcoming', 'ongoing')
    )
    
    event['status_label'] = EVENT_STATUSES.get(event.get('status'), event.get('status'))
    event['category_label'] = EVENT_CATEGORIES.get(event.get('category'), event.get('category'))
    event['is_creator'] = is_creator
    event['is_participant'] = is_participant
    event['can_join'] = can_join
    event['can_leave'] = can_leave
    event['spaces_remaining'] = None if event['max_participants'] is None else max(0, event['max_participants'] - event['participant_count'])
    event['is_full'] = event['max_participants'] is not None and event['participant_count'] >= event['max_participants']
    
    return render_template('events_detail.html', event=event, participants=participants)

@app.route('/events/<int:event_id>/join', methods=['POST'])
def join_event(event_id):
    """Join an event"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_uid = session['user_id']
    event = query_db('SELECT * FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events_browse'))
    
    # Check if already participant
    already_joined = query_db(
        'SELECT id FROM event_participants WHERE event_id = ? AND user_id = ?',
        (event_id, current_uid),
        one=True
    )
    
    if already_joined:
        flash('You are already a participant in this event.', 'info')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Check if user is creator
    if event['creator_id'] == current_uid:
        flash('You cannot join your own event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Check capacity
    participant_count = query_db(
        'SELECT COUNT(*) as c FROM event_participants WHERE event_id = ?',
        (event_id,),
        one=True
    )['c']
    
    if event['max_participants'] and participant_count >= event['max_participants']:
        flash('This event is full.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Check status
    if event['status'] not in ('upcoming', 'ongoing'):
        flash('You cannot join this event (status: ' + event['status'] + ').', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Add participant
    now = datetime.now().isoformat()
    query_db(
        'INSERT INTO event_participants (event_id, user_id, joined_at) VALUES (?, ?, ?)',
        (event_id, current_uid, now)
    )
    
    flash('You have joined the event!', 'success')
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/events/<int:event_id>/leave', methods=['POST'])
def leave_event(event_id):
    """Leave an event"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_uid = session['user_id']
    event = query_db('SELECT * FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events_browse'))
    
    # Check if user is creator
    if event['creator_id'] == current_uid:
        flash('You cannot leave an event you created. Delete it instead.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))

    # Check if user is participant
    participant = query_db(
        'SELECT id FROM event_participants WHERE event_id = ? AND user_id = ?',
        (event_id, current_uid),
        one=True
    )
    
    if not participant:
        flash('You are not a participant in this event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Check if event has started (can only leave upcoming/ongoing)
    if event['status'] not in ('upcoming', 'ongoing'):
        flash('Cannot leave a past or cancelled event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Remove participant
    query_db(
        'DELETE FROM event_participants WHERE event_id = ? AND user_id = ?',
        (event_id, current_uid)
    )
    
    flash('You have left the event.', 'success')
    return redirect(url_for('events_browse'))

@app.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    """Edit an event (creator only)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event = query_db('SELECT * FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events_browse'))
    
    if event['creator_id'] != session['user_id']:
        flash('Only the creator can edit this event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Cannot edit past events
    if event['status'] == 'past':
        flash('Cannot edit a past event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        location_name = request.form.get('location_name', '').strip()
        city = request.form.get('city', '').strip()  # NEW: city field
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        max_participants = request.form.get('max_participants', '').strip()
        
        # Validation
        errors = []
        if not title or len(title) < 3:
            errors.append('Title must be at least 3 characters.')
        if not description or len(description) < 10:
            errors.append('Description must be at least 10 characters.')
        if not event_date:
            errors.append('Event date/time is required.')
        if not location_name or len(location_name) < 3:
            errors.append('Location name is required.')
        if not city or len(city) < 2:
            errors.append('City is required.')
        
        # Coordinates are now optional
        lat = None
        lon = None
        if latitude or longitude:
            try:
                lat = float(latitude)
                lon = float(longitude)
                if lat < -90 or lat > 90 or lon < -180 or lon > 180:
                    errors.append('Invalid coordinates.')
            except ValueError:
                errors.append('Coordinates must be valid numbers if provided.')
        
        max_part = event['max_participants']  # Keep existing if not updated
        if max_participants:
            try:
                max_part = int(max_participants)
                if max_part <= 0:
                    errors.append('Max participants must be positive.')
                # Check if new limit is below current participants
                current_count = query_db(
                    'SELECT COUNT(*) as c FROM event_participants WHERE event_id = ?',
                    (event_id,),
                    one=True
                )['c']
                if max_part < current_count:
                    errors.append(f'New limit ({max_part}) is below current participants ({current_count}).')
            except ValueError:
                errors.append('Max participants must be a number.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('edit_event', event_id=event_id))
        
        # Handle cover image update
        cover_image = event['cover_image']
        file = request.files.get('cover_image')
        if file and file.filename and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f"event_{session['user_id']}_{int(datetime.now().timestamp())}_{fn}")
            file.save(dest)
            rel = os.path.relpath(dest, start='static').replace('\\', '/')
            cover_image = f"/static/{rel}"
        
        now = datetime.now().isoformat()
        query_db('''
            UPDATE events
            SET title = ?, description = ?, event_date = ?, location_name = ?,
                city = ?, latitude = ?, longitude = ?, max_participants = ?, cover_image = ?, updated_at = ?
            WHERE id = ?
        ''', (title, description, event_date, location_name, city, lat, lon, max_part, cover_image, now, event_id))
        
        flash('Event updated successfully!', 'success')
        return redirect(url_for('event_detail', event_id=event_id))
    
    return render_template('events_edit.html', event=event, categories=EVENT_CATEGORIES)

@app.route('/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    """Delete an event (creator only)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    event = query_db('SELECT * FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events_browse'))
    
    if event['creator_id'] != session['user_id']:
        flash('Only the creator can delete this event.', 'error')
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Delete event (cascades to participants due to FK constraint)
    query_db('DELETE FROM events WHERE id = ?', (event_id,))
    
    flash('Event deleted.', 'success')
    return redirect(url_for('events_browse'))

@app.route('/my-events')
def my_events():
    """View user's created and joined events"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_uid = session['user_id']
    tab = request.args.get('tab', 'created')  # 'created' or 'joined'
    
    if tab == 'joined':
        # Events user has joined
        events = query_db('''
            SELECT e.*, u.username as creator_username, u.profile_pic as creator_pic,
                   COUNT(DISTINCT ep.user_id) as participant_count
            FROM events e
            JOIN users u ON e.creator_id = u.id
            JOIN event_participants ep_user ON e.id = ep_user.event_id AND ep_user.user_id = ?
            LEFT JOIN event_participants ep ON e.id = ep.event_id
            GROUP BY e.id
            ORDER BY e.event_date ASC
        ''', (current_uid,))
        event_type = 'joined'
    else:  # 'created'
        # Events user has created
        events = query_db('''
            SELECT e.*, u.username as creator_username, u.profile_pic as creator_pic,
                   COUNT(DISTINCT ep.user_id) as participant_count
            FROM events e
            JOIN users u ON e.creator_id = u.id
            LEFT JOIN event_participants ep ON e.id = ep.event_id
            WHERE e.creator_id = ?
            GROUP BY e.id
            ORDER BY e.event_date ASC
        ''', (current_uid,))
        event_type = 'created'
    
    for event in events:
        event['status_label'] = EVENT_STATUSES.get(event['status'], event['status'])
        event['category_label'] = EVENT_CATEGORIES.get(event['category'], event['category'])
    
    return render_template('my_events.html', events=events, tab=tab, event_type=event_type)

if __name__ == '__main__':
    # NOTE: use debug=True for local development; remove or set False in production.
    app.run(debug=True, host='127.0.0.1', port=5000)
