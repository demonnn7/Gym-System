from flask import Flask, render_template, url_for, request, redirect, session
import psycopg2
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 设置一个密钥用于会话管理

TRANSACTION_POOLER_URI = (
    "postgresql://postgres.gmevpselpkclylnjgity:abc14789sysu@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
)

def get_db_connection():
    """创建数据库连接（使用Transaction Pooler）"""
    try:
        # Transaction Pooler URI
        conn = psycopg2.connect(
            TRANSACTION_POOLER_URI,
            sslmode="require",  # 启用SSL加密
            connect_timeout=5    # 5秒连接超时
        )
        return conn
    except psycopg2.Error as e:
        print(f"数据库连接失败: {e}")
        
        # 如果失败，尝试回退到 Pooler 的参数化连接
        try:
            return psycopg2.connect(
                dbname="postgres",
                user="postgres.gmevpselpkclylnjgity",
                password="abc14789sysu",
                host="aws-0-ap-southeast-1.pooler.supabase.com",
                port="6543",
                sslmode="require"
            )
        except psycopg2.Error as fallback_error:
            print(f"回退连接失败: {fallback_error}")
            return None

# 确保静态文件路径正确
@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT role FROM Users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        if user:
            session['role'] = user[0]  # 将用户角色存储在会话中
            if user[0] == 'admin':
                return redirect(url_for('manage_members'))
            else:
                # 从 Members 表中根据用户名查找 member_id
                cursor.execute('SELECT member_id FROM Members WHERE name = %s', (username,))
                member_info = cursor.fetchone()
                if member_info:
                    session['member_id'] = member_info[0]  # 将 member_id 存储在会话中
                    return redirect(url_for('view_courses'))
                else:
                    return "Member not found.", 404
        else:
            return "Invalid username or password.", 401
    except psycopg2.Error as e:
        print(f"An error occurred while logging in: {e}")
        return "Failed to log in.", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/members')
def manage_members():
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT member_id, name, gender, age, contact, membership_level FROM Members;')
        members = [{'member_id': row[0], 'name': row[1], 'gender': row[2], 'age': row[3], 'contact': row[4], 'membership_level': row[5]} for row in cursor.fetchall()]
    except psycopg2.Error as e:
        print(f"An error occurred while fetching members: {e}")
        return "Failed to fetch members from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return render_template('members.html', members=members)


@app.route('/members/add', methods=['GET', 'POST'])
def add_member():
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    if request.method == 'GET':
        return render_template('add_member.html')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        name = request.form['name']
        gender = request.form['gender']
        age = request.form['age']
        contact = request.form['contact']
        membership_level = request.form['membership_level']
        # 设置默认密码为 666666 的哈希值
        default_password = '666666'
        # 先向 Users 表添加用户信息
        cursor.execute(
            "INSERT INTO Users (username, password, role) VALUES (%s, %s, %s)",
            (name, default_password, 'user')
        )
        # 再向 Members 表添加成员信息
        cursor.execute(
            "INSERT INTO Members (name, gender, age, contact, membership_level) VALUES (%s, %s, %s, %s, %s)",
            (name, gender, age, contact, membership_level)
        )
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while adding a member: {e}")
        conn.rollback()
        return "Failed to add a member to the database.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_members'))


@app.route('/members/edit/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    if request.method == 'POST':
        try:
            gender = request.form['gender']
            age = request.form['age']
            contact = request.form['contact']
            membership_level = request.form['membership_level']
            cursor.execute(
                "UPDATE Members SET gender = %s, age = %s, contact = %s, membership_level = %s WHERE member_id = %s",
                ( gender, age, contact, membership_level, member_id)
            )
            conn.commit()
            return redirect(url_for('manage_members'))
        except psycopg2.Error as e:
            print(f"An error occurred while editing a member: {e}")
            conn.rollback()
            return "Failed to edit a member in the database.", 500
    else:
        try:
            cursor.execute('SELECT member_id, name, gender, age, contact, membership_level FROM Members WHERE member_id = %s', (member_id,))
            member = cursor.fetchone()
            if member is None:
                return "Member not found.", 404
            member = {'member_id': member[0], 'name': member[1], 'gender': member[2], 'age': member[3], 'contact': member[4], 'membership_level': member[5]}
        except psycopg2.Error as e:
            print(f"An error occurred while fetching a member for editing: {e}")
            return "Failed to fetch a member for editing from the database.", 500
        finally:
            cursor.close()
            conn.close()
    return render_template('edit_member.html', member=member)


@app.route('/members/delete/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 首先删除 Users 表中的用户信息，假设可以通过 member_id 关联
        cursor.execute('DELETE FROM Users WHERE username IN (SELECT name FROM Members WHERE member_id = %s)', (member_id,))
        # 然后删除 Members 表中的成员信息
        cursor.execute('DELETE FROM Members WHERE member_id = %s', (member_id,))
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while deleting a member: {e}")
        conn.rollback()
        return "Failed to delete a member from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('manage_members'))

@app.route('/search_members', methods=['GET'])
def search_members():
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    search_query = request.args.get('search')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        if search_query:
            # 搜索用户
            cursor.execute('''
                SELECT *
                FROM Members
                WHERE name ILIKE %s
            ''', (f'%{search_query}%',))
        else:
            # 如果没有搜索内容，显示全部用户
            cursor.execute('SELECT * FROM Members')
        members = []
        for row in cursor.fetchall():
            members.append({
                'member_id': row[0],
                'name': row[1],
                'gender': row[2],
                'age': row[3],
                'contact': row[4],
                'membership_level': row[5]
            })
    except psycopg2.Error as e:
        print(f"An error occurred while searching members: {e}")
        return "Failed to search members from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return render_template('members.html', members=members, current_page='members')


@app.route('/view_courses')
def view_courses():
    if 'role' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 获取课程信息
        cursor.execute('''
            SELECT c.course_id, c.course_name, c.duration, c.coach, c.price
            FROM Courses c
        ''')
        courses = []
        for row in cursor.fetchall():
            courses.append({
                'course_id': row[0],
                'course_name': row[1],
                'duration': row[2],
                'coach': row[3],
                'price': row[4]
            })
    except psycopg2.Error as e:
        print(f"An error occurred while fetching courses: {e}")
        return "Failed to fetch courses from the database.", 500
    finally:
        cursor.close()
        conn.close()
    # 将 is_reserved_by_current_user 函数传递给模板
    return render_template('courses.html', courses=courses, current_page='courses', is_reserved_by_current_user=is_reserved_by_current_user)

@app.route('/courses/add', methods=['GET', 'POST'])
def add_course():
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    if request.method == 'GET':
        return render_template('add_courses.html')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        course_name = request.form['course_name']
        duration = request.form['duration']
        coach = request.form['coach']
        price = request.form['price']
        cursor.execute(
            "INSERT INTO Courses (course_name, duration, coach, price) VALUES (%s, %s, %s, %s)",
            (course_name, duration, coach, price)
        )
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while adding a course: {e}")
        conn.rollback()
        return "Failed to add a course to the database.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('view_courses'))


@app.route('/courses/edit/<int:course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    if request.method == 'POST':
        try:
            course_name = request.form['course_name']
            duration = request.form['duration']
            coach = request.form['coach']
            price = request.form['price']
            cursor.execute(
                "UPDATE Courses SET course_name = %s, duration = %s, coach = %s, price = %s WHERE course_id = %s",
                (course_name, duration, coach, price, course_id)
            )
            conn.commit()
            return redirect(url_for('view_courses'))
        except psycopg2.Error as e:
            print(f"An error occurred while editing a course: {e}")
            conn.rollback()
            return "Failed to edit a course in the database.", 500
    else:
        try:
            cursor.execute('SELECT course_id, course_name, duration, coach, price FROM Courses WHERE course_id = %s', (course_id,))
            course = cursor.fetchone()
            if course is None:
                return "Course not found.", 404
            course = {'course_id': course[0], 'course_name': course[1], 'duration': course[2], 'coach': course[3], 'price': course[4]}
        except psycopg2.Error as e:
            print(f"An error occurred while fetching a course for editing: {e}")
            return "Failed to fetch a course for editing from the database.", 500
        finally:
            cursor.close()
            conn.close()
    return render_template('edit_courses.html', course=course)


@app.route('/courses/delete/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    if 'role' not in session or session['role']!= 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM Courses WHERE course_id = %s', (course_id,))
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while deleting a course: {e}")
        conn.rollback()
        return "Failed to delete a course from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('view_courses'))

@app.route('/search_courses', methods=['GET'])
def search_courses():
    if 'role' not in session:
        return redirect(url_for('login'))
    search_query = request.args.get('search')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        if search_query:
            # 搜索课程
            cursor.execute('''
                SELECT c.course_id, c.course_name, c.duration, c.coach, c.price, 
                       EXISTS (
                           SELECT 1 FROM Reservations r
                           WHERE r.member_id = %s AND r.course_id = c.course_id
                       ) AS is_reserved
                FROM Courses c
                WHERE c.course_name ILIKE %s
            ''', (session.get('member_id'), f'%{search_query}%'))
        else:
            # 如果没有搜索内容，显示全部课程
            cursor.execute('''
                SELECT c.course_id, c.course_name, c.duration, c.coach, c.price, 
                       EXISTS (
                           SELECT 1 FROM Reservations r
                           WHERE r.member_id = %s AND r.course_id = c.course_id
                       ) AS is_reserved
                FROM Courses c
            ''', (session.get('member_id'),))
        courses = []
        for row in cursor.fetchall():
            courses.append({
                'course_id': row[0],
                'course_name': row[1],
                'duration': row[2],
                'coach': row[3],
                'price': row[4],
                'is_reserved': row[5]
            })
    except psycopg2.Error as e:
        print(f"An error occurred while searching courses: {e}")
        return "Failed to search courses from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return render_template('courses.html', courses=courses, current_page='courses')

@app.route('/profile')
def view_profile():
    if 'role' not in session:
        return redirect(url_for('login'))
    member_id = session.get('member_id')  # 假设我们存储了用户的 member_id 在会话中
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 移除对 member_id 的查询，只查询用户的其他信息
        cursor.execute('SELECT name, gender, age, contact, membership_level FROM Members WHERE member_id = %s', (member_id,))
        member = cursor.fetchone()
        if member is None:
            return "Member not found.", 404
        # 只存储所需的用户信息，不包括 member_id
        member = {'name': member[0], 'gender': member[1], 'age': member[2], 'contact': member[3], 'membership_level': member[4]}
    except psycopg2.Error as e:
        print(f"An error occurred while fetching a member for profile: {e}")
        return "Failed to fetch a member for profile from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return render_template('profile.html', member=member)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'role' not in session:
        return redirect(url_for('login'))
    member_id = session.get('member_id')  # 假设我们存储了用户的 member_id 在会话中
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    if request.method == 'GET':
        # 获取当前用户信息
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT contact FROM Members WHERE member_id = %s', (member_id,))
            contact = cursor.fetchone()[0]
        except psycopg2.Error as e:
            print(f"An error occurred while fetching contact for edit profile: {e}")
            return "Failed to fetch contact for edit profile from the database.", 500
        finally:
            cursor.close()
        return render_template('edit_profile.html', contact=contact)
    elif request.method == 'POST':
        # 处理用户提交的修改信息
        new_contact = request.form.get('contact')
        new_password = request.form.get('password')
        cursor = conn.cursor()
        try:
            # 更新 Members 表中的联系电话
            cursor.execute('UPDATE Members SET contact = %s WHERE member_id = %s', (new_contact, member_id))
            # 更新 Users 表中的密码，假设通过 member_id 关联 Users 和 Members 表
            cursor.execute('UPDATE Users SET password = %s WHERE username = (SELECT name FROM Members WHERE member_id = %s)', (new_password, member_id))
            conn.commit()  # 提交事务，保存修改
            return redirect(url_for('view_profile'))  # 修改完成后重定向到个人信息页面
        except psycopg2.Error as e:
            print(f"An error occurred while updating profile: {e}")
            conn.rollback()  # 出现错误时回滚事务
            return "Failed to update profile in the database.", 500
        finally:
            cursor.close()
        conn.close()


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('role', None)  # 清除用户角色信息
    return render_template('login.html')

@app.route('/reservations_by_member/<int:member_id>')
def view_reservations_by_member(member_id):
    if 'role' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 获取预约信息，同时关联 Courses 表获取课程名称、课程时长和教练信息
        cursor.execute('''
            SELECT r.reservation_id, r.course_id, c.course_name, c.duration AS course_duration, c.coach, r.reservation_time
            FROM Reservations r
            JOIN Courses c ON r.course_id = c.course_id
            WHERE r.member_id = %s
        ''', (member_id,))
        reservations = [{'reservation_id': row[0], 'course_id': row[1], 'course_name': row[2], 'course_duration': row[3], 'coach': row[4], 'reservation_time': row[5]} for row in cursor.fetchall()]
        # 获取 member 信息
        cursor.execute('SELECT name FROM Members WHERE member_id = %s', (member_id,))
        member = cursor.fetchone()
    except psycopg2.Error as e:
        print(f"An error occurred while fetching reservations: {e}")
        return "Failed to fetch reservations from the database.", 500
    finally:
        cursor.close()
        conn.close()
    return render_template('view_reservations_by_member.html', reservations=reservations, member_id=member_id, member={'name': member[0]})

@app.route('/make_reservation/<int:course_id>', methods=['POST'])
def make_reservation(course_id):
    if 'role' not in session or session['role']!= 'user':
        return redirect(url_for('login'))
    member_id = session.get('member_id')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 插入预约记录，不检查课程是否已被其他用户预约
        cursor.execute('''
            INSERT INTO Reservations (member_id, course_id, reservation_time)
            VALUES (%s, %s, NOW())
        ''', (member_id, course_id))
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while making a reservation: {e}")
        conn.rollback()
        return "Failed to make a reservation.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('view_courses'))


@app.route('/cancel_reservation/<int:course_id>', methods=['POST'])
def cancel_reservation(course_id):
    if 'role' not in session or session['role']!= 'user':
        return redirect(url_for('login'))
    member_id = session.get('member_id')
    conn = get_db_connection()
    if conn is None:
        return "Failed to connect to the database.", 500
    cursor = conn.cursor()
    try:
        # 删除当前用户对该课程的预约记录
        cursor.execute('''
            DELETE FROM Reservations
            WHERE member_id = %s AND course_id = %s
        ''', (member_id, course_id))
        conn.commit()
    except psycopg2.Error as e:
        print(f"An error occurred while canceling a reservation: {e}")
        conn.rollback()
        return "Failed to cancel a reservation.", 500
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('view_courses'))

def is_reserved_by_current_user(course_id):
    if 'role' not in session or session['role']!= 'user':
        return False
    member_id = session.get('member_id')
    conn = get_db_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT 1 FROM Reservations
            WHERE member_id = %s AND course_id = %s
        ''', (member_id, course_id))
        result = cursor.fetchone()
        return result is not None
    except psycopg2.Error as e:
        print(f"An error occurred while checking reservation: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)