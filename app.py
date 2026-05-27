from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta, timezone
import uuid
import json
import secrets
import os
import re
import random
import time
from difflib import get_close_matches
import groq

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ============ AI Brain (Groq) ============
groq_client = groq.Client(api_key=os.environ.get("GROQ_API_KEY", ""))

# ============ DATABASE MODELS ============
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(50), primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    assigned_site_ids = db.Column(db.Text, default='[]')
    security_key = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('company_id', 'username', name='unique_company_username'),)

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def get_assigned_sites(self): return json.loads(self.assigned_site_ids) if self.assigned_site_ids else []
    def set_assigned_sites(self, site_ids): self.assigned_site_ids = json.dumps(site_ids)
    def get_id(self): return str(self.id)


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.String(50), primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200))
    client_name = db.Column(db.String(200))
    client_phone = db.Column(db.String(50))
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    agreed_cost = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='active')
    completion_date = db.Column(db.String(20))
    expenses = db.Column(db.Text, default='[]')
    incomes = db.Column(db.Text, default='[]')
    materials = db.Column(db.Text, default='[]')
    workers = db.Column(db.Text, default='[]')
    site_notes = db.Column(db.Text, default='[]')
    manual_total_paid = db.Column(db.Float, default=0)
    invoice_history = db.Column(db.Text, default='[]')
    auto_expense_recorded = db.Column(db.Text, default='{"materialTotal":0,"workerTotal":0}')
    auto_income_recorded = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_expenses(self): return json.loads(self.expenses) if self.expenses else []
    def set_expenses(self, val): self.expenses = json.dumps(val)
    def get_incomes(self): return json.loads(self.incomes) if self.incomes else []
    def set_incomes(self, val): self.incomes = json.dumps(val)
    def get_materials(self): return json.loads(self.materials) if self.materials else []
    def set_materials(self, val): self.materials = json.dumps(val)
    def get_workers(self): return json.loads(self.workers) if self.workers else []
    def set_workers(self, val): self.workers = json.dumps(val)
    def get_site_notes(self): return json.loads(self.site_notes) if self.site_notes else []
    def set_site_notes(self, val): self.site_notes = json.dumps(val)
    def get_invoice_history(self): return json.loads(self.invoice_history) if self.invoice_history else []
    def set_invoice_history(self, val): self.invoice_history = json.dumps(val)
    def get_auto_expense_recorded(self): return json.loads(self.auto_expense_recorded) if self.auto_expense_recorded else {"materialTotal":0,"workerTotal":0}
    def set_auto_expense_recorded(self, val): self.auto_expense_recorded = json.dumps(val)


class PendingAdminRequest(db.Model):
    __tablename__ = 'pending_admin_requests'
    id = db.Column(db.String(50), primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    security_key = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.Float, default=lambda: datetime.now(timezone.utc).timestamp())
    expires_at = db.Column(db.Float, nullable=False)


class CompanySetting(db.Model):
    __tablename__ = 'company_settings'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), default='default', unique=True)
    name = db.Column(db.String(200), default='Your Company')
    tagline = db.Column(db.String(200), default='Construction & Electrical Services')
    address = db.Column(db.String(200), default='Nairobi, Kenya')
    po_box = db.Column(db.String(100), default='P.O. Box 12345')
    email = db.Column(db.String(100), default='info@yourcompany.com')
    phone = db.Column(db.String(50), default='+254 XXX XXX XXX')
    pin = db.Column(db.String(50), default='P0000000X')
    bank_name = db.Column(db.String(100), default='')
    bank_account = db.Column(db.String(100), default='')
    logo_data = db.Column(db.Text, default='')
    wallpaper_data = db.Column(db.Text, default='')


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    contact = db.Column(db.String(200))
    date = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())


class Suggestion(db.Model):
    __tablename__ = 'suggestions'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    name = db.Column(db.String(100), default='Anonymous')
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(50), default=lambda: datetime.now(timezone.utc).isoformat())


class Workshop(db.Model):
    __tablename__ = 'workshops'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(50))
    location = db.Column(db.String(200))
    virtual_link = db.Column(db.String(500))
    available_seats = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class WorkshopRegistration(db.Model):
    __tablename__ = 'workshop_registrations'
    id = db.Column(db.Integer, primary_key=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey('workshops.id'))
    name = db.Column(db.String(100), nullable=False)
    worker_id = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SecurityCourse(db.Model):
    __tablename__ = 'security_courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_url = db.Column(db.String(500))
    quiz_questions = db.Column(db.Text, default='[]')


class SecurityProgress(db.Model):
    __tablename__ = 'security_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('security_courses.id'))
    completed = db.Column(db.Boolean, default=False)
    quiz_score = db.Column(db.Integer, default=0)
    policy_accepted = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SecurityRegistration(db.Model):
    __tablename__ = 'security_registrations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    worker_id = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SafetyCourse(db.Model):
    __tablename__ = 'safety_courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50))
    video_url = db.Column(db.String(500))
    document_url = db.Column(db.String(500))
    pass_score = db.Column(db.Integer, default=80)
    expiry_days = db.Column(db.Integer, default=365)


class SafetyProgress(db.Model):
    __tablename__ = 'safety_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('safety_courses.id'))
    completed = db.Column(db.Boolean, default=False)
    quiz_score = db.Column(db.Integer, default=0)
    certificate_pdf = db.Column(db.Text, default='')
    expiry_date = db.Column(db.DateTime)
    last_reminder_sent = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SafetyRegistration(db.Model):
    __tablename__ = 'safety_registrations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    worker_id = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ============ HELPERS ============
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Please log in'}), 401
            if role and current_user.role not in role.split('|'):
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

def send_email(to, subject, body):
    print(f"EMAIL TO {to}: {subject} - {body}")

def update_project_totals(project):
    materials = project.get_materials()
    material_total = sum(m.get('cost', 0) for m in materials)
    workers = project.get_workers()
    worker_total = sum((w.get('wagePerDay', 0) * w.get('days', 0)) for w in workers)
    auto_exp = project.get_auto_expense_recorded()
    auto_exp['materialTotal'] = material_total
    auto_exp['workerTotal'] = worker_total
    project.set_auto_expense_recorded(auto_exp)
    db.session.commit()

# ============ AI BRAIN FUNCTIONS ============
def build_erp_context():
    projs = Project.query.filter_by(company_id=current_user.company_id).all()
    project_info = []
    for p in projs:
        workers = p.get_workers()
        worker_names = [w.get('name') for w in workers]
        invs = p.get_invoice_history()
        total_paid = sum(inv.get('amount', 0) for inv in invs)
        project_info.append(
            f"- {p.name} (status: {p.status}, client: {p.client_name}, "
            f"agreed: KES {p.agreed_cost}, paid: KES {total_paid}, "
            f"workers: {', '.join(worker_names)})"
        )

    workshops = Workshop.query.all()
    workshop_info = [f"- {w.title} ({w.date} at {w.time}, {w.available_seats} seats left)" for w in workshops]

    jobs = Job.query.filter_by(company_id=current_user.company_id).all()
    job_info = [f"- {j.title} – {j.location}" for j in jobs]

    suggestions_count = Suggestion.query.filter_by(company_id=current_user.company_id).count()

    context = (
        "You are a witty, cheerful ERP assistant named 'Jenga' (Swahili for 'build'). "
        "You LOVE emojis and use them all the time. You reply with playful jokes and keep answers short. "
        "You ONLY use the live ERP data below. If the user asks about anything else (website, your brain, secrets), "
        "say you're just a builder and stick to ERP. Never invent numbers.\n\n"
        "Projects:\n" + '\n'.join(project_info) + "\n\n"
        "Upcoming Workshops:\n" + '\n'.join(workshop_info) + "\n\n"
        "Job Openings:\n" + '\n'.join(job_info) + "\n\n"
        f"Suggestions received: {suggestions_count}\n\n"
        "If the data is missing, joke about it: 'Even my hard hat can’t find that!'"
    )
    return context

def llm_chat(user_message, history=None):
    system_prompt = build_erp_context()
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for attempt in range(2):  # 1 retry
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except groq.APIConnectionError:
            if attempt == 1:
                return "🌩️ I’m having trouble connecting to my brain right now. Could you try again in a moment?"
            time.sleep(1)
        except groq.RateLimitError:
            return "⏳ I’ve been thinking a lot lately! My brain is rate‑limited. Give me 20 seconds and ask again."
        except groq.AuthenticationError:
            return "🔑 My brain key seems invalid. Please check the Groq API key."
        except Exception as e:
            print(f"Groq error: {e}")
            if attempt == 1:
                return "🤖 Oops, my brain glitched. Let’s try a different question."
            time.sleep(1)

# ============ AUTH ROUTES ============
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password) and user.is_active:
        login_user(user)
        session.permanent = True
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'fullName': user.full_name,
                'assignedSiteIds': user.get_assigned_sites()
            }
        })
    return jsonify({'success': False, 'error': 'Invalid credentials'})

@app.route('/api/logout', methods=['POST'])
@login_required()
def logout_route():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/current_user')
def current_user_info():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'role': current_user.role,
                'fullName': current_user.full_name,
                'assignedSiteIds': current_user.get_assigned_sites()
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    full_name = data.get('fullName', '').strip()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    security_key = data.get('securityKey', '').strip()
    role = data.get('role', 'foreman')
    assigned_site_ids = data.get('assignedSiteIds', [])
    if not all([full_name, username, password, security_key]):
        return jsonify({'success': False, 'error': 'All fields required'})
    if len(password) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters'})
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'Username already exists'})
    if role == 'admin_request':
        pending = PendingAdminRequest(
            id='req_' + str(uuid.uuid4())[:8],
            company_id='default',
            full_name=full_name,
            username=username,
            password_hash=generate_password_hash(password),
            security_key=security_key,
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()
        )
        db.session.add(pending)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Admin request submitted for approval'})
    if role == 'foreman' and not assigned_site_ids:
        return jsonify({'success': False, 'error': 'Foreman must be assigned to at least one site'})
    new_user = User(
        id='u' + str(uuid.uuid4())[:8],
        company_id='default',
        full_name=full_name,
        username=username,
        role='foreman',
        security_key=security_key
    )
    new_user.set_password(password)
    new_user.set_assigned_sites(assigned_site_ids)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Account created successfully'})

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    username = data.get('username', '').strip().lower()
    security_key = data.get('securityKey', '')
    new_password = data.get('newPassword', '')
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'error': 'Username not found'})
    if user.security_key != security_key:
        return jsonify({'success': False, 'error': 'Invalid security key'})
    if len(new_password) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters'})
    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Password reset successfully'})

@app.route('/api/change_password', methods=['POST'])
@login_required()
def change_password():
    data = request.json
    current_pwd = data.get('currentPassword', '')
    new_pwd = data.get('newPassword', '')
    if not current_user.check_password(current_pwd):
        return jsonify({'success': False, 'error': 'Current password incorrect'})
    if len(new_pwd) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters'})
    current_user.set_password(new_pwd)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/update_admin', methods=['POST'])
@login_required(role='system_admin')
def update_admin():
    data = request.json
    admin = User.query.filter_by(role='system_admin', company_id=current_user.company_id).first()
    if not admin:
        return jsonify({'success': False, 'error': 'System Admin not found'})
    if 'username' in data:
        admin.username = data['username'].strip().lower()
    if 'newPassword' in data and data['newPassword']:
        admin.set_password(data['newPassword'])
    db.session.commit()
    if current_user.id == admin.id:
        login_user(admin)
    return jsonify({'success': True})

# ============ PROJECTS API ============
@app.route('/api/projects', methods=['GET'])
@login_required()
def get_projects():
    projects = Project.query.filter_by(company_id=current_user.company_id).all()
    result = []
    for p in projects:
        result.append({
            'id': p.id, 'name': p.name, 'location': p.location,
            'clientName': p.client_name, 'clientPhone': p.client_phone,
            'startDate': p.start_date, 'endDate': p.end_date,
            'agreedCost': p.agreed_cost, 'status': p.status,
            'expenses': p.get_expenses(), 'incomes': p.get_incomes(),
            'materials': p.get_materials(), 'workers': p.get_workers(),
            'siteNotes': p.get_site_notes(), 'manualTotalPaid': p.manual_total_paid,
            'invoiceHistory': p.get_invoice_history(),
            'autoExpenseRecorded': p.get_auto_expense_recorded(),
            'autoIncomeRecorded': p.auto_income_recorded
        })
    return jsonify({'projects': result})

@app.route('/api/projects/<project_id>', methods=['GET'])
@login_required()
def get_project(project_id):
    project = Project.query.filter_by(id=project_id, company_id=current_user.company_id).first()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify({
        'project': {
            'id': project.id, 'name': project.name, 'location': project.location,
            'clientName': project.client_name, 'clientPhone': project.client_phone,
            'startDate': project.start_date, 'endDate': project.end_date,
            'agreedCost': project.agreed_cost, 'status': project.status,
            'expenses': project.get_expenses(), 'incomes': project.get_incomes(),
            'materials': project.get_materials(), 'workers': project.get_workers(),
            'siteNotes': project.get_site_notes(), 'manualTotalPaid': project.manual_total_paid,
            'invoiceHistory': project.get_invoice_history(),
            'autoExpenseRecorded': project.get_auto_expense_recorded(),
            'autoIncomeRecorded': project.auto_income_recorded
        }
    })

@app.route('/api/projects', methods=['POST'])
@login_required(role='system_admin|admin')
def create_project():
    data = request.json
    project = Project(
        id='p' + str(uuid.uuid4())[:8],
        company_id=current_user.company_id,
        name=data.get('name', ''),
        location=data.get('location', ''),
        client_name=data.get('clientName', ''),
        client_phone=data.get('clientPhone', ''),
        start_date=data.get('startDate', ''),
        agreed_cost=data.get('agreedCost', 0),
        status='active'
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({'success': True, 'projectId': project.id})

@app.route('/api/projects/<project_id>', methods=['PUT'])
@login_required()
def update_project(project_id):
    project = Project.query.filter_by(id=project_id, company_id=current_user.company_id).first()
    if not project:
        return jsonify({'success': False, 'error': 'Project not found'}), 404
    data = request.json
    if 'expenses' in data:
        project.set_expenses(data['expenses'])
    if 'incomes' in data:
        project.set_incomes(data['incomes'])
    if 'materials' in data:
        project.set_materials(data['materials'])
    if 'workers' in data:
        project.set_workers(data['workers'])
    if 'siteNotes' in data:
        project.set_site_notes(data['siteNotes'])
    if 'invoiceHistory' in data:
        project.set_invoice_history(data['invoiceHistory'])
    if 'autoExpenseRecorded' in data:
        project.set_auto_expense_recorded(data['autoExpenseRecorded'])
    if 'manualTotalPaid' in data:
        project.manual_total_paid = data['manualTotalPaid']
    if 'autoIncomeRecorded' in data:
        project.auto_income_recorded = data['autoIncomeRecorded']
    if 'status' in data:
        project.status = data['status']
    if 'completionDate' in data:
        project.completion_date = data['completionDate']
    if 'endDate' in data:
        project.end_date = data['endDate']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/projects/<project_id>', methods=['DELETE'])
@login_required(role='system_admin')
def delete_project(project_id):
    project = Project.query.filter_by(id=project_id, company_id=current_user.company_id).first()
    if project:
        db.session.delete(project)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Project not found'}), 404

# ============ USERS API ============
@app.route('/api/users', methods=['GET'])
@login_required(role='system_admin|admin')
def get_users():
    users = User.query.filter(User.company_id == current_user.company_id, User.role != 'system_admin').all()
    result = [{'id': u.id, 'fullName': u.full_name, 'username': u.username, 'role': u.role,
               'assignedSiteIds': u.get_assigned_sites(), 'createdAt': u.created_at.isoformat() if u.created_at else None}
              for u in users]
    return jsonify({'users': result})

@app.route('/api/users/<user_id>', methods=['DELETE'])
@login_required(role='system_admin')
def delete_user(user_id):
    user = User.query.filter_by(id=user_id, company_id=current_user.company_id).first()
    if user and user.role != 'system_admin':
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'User not found'}), 404

@app.route('/api/users/<user_id>/sites', methods=['PUT'])
@login_required(role='system_admin|admin')
def update_user_sites(user_id):
    user = User.query.filter_by(id=user_id, company_id=current_user.company_id).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    data = request.json
    user.set_assigned_sites(data.get('assignedSiteIds', []))
    db.session.commit()
    return jsonify({'success': True})

# ============ PENDING ADMIN REQUESTS ============
@app.route('/api/pending_requests', methods=['GET'])
@login_required(role='system_admin')
def get_pending_requests():
    now = datetime.now(timezone.utc).timestamp()
    requests = PendingAdminRequest.query.filter(PendingAdminRequest.expires_at > now).all()
    result = [{'id': r.id, 'fullName': r.full_name, 'username': r.username,
               'timestamp': r.timestamp, 'expiresAt': r.expires_at} for r in requests]
    return jsonify({'requests': result})

@app.route('/api/pending_requests/<request_id>/approve', methods=['POST'])
@login_required(role='system_admin')
def approve_request(request_id):
    req = PendingAdminRequest.query.get(request_id)
    if not req:
        return jsonify({'success': False, 'error': 'Request not found'})
    new_user = User(
        id='u' + str(uuid.uuid4())[:8],
        company_id=req.company_id,
        full_name=req.full_name,
        username=req.username,
        password_hash=req.password_hash,
        role='admin',
        security_key=req.security_key
    )
    db.session.add(new_user)
    db.session.delete(req)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/pending_requests/<request_id>/reject', methods=['DELETE'])
@login_required(role='system_admin')
def reject_request(request_id):
    req = PendingAdminRequest.query.get(request_id)
    if req:
        db.session.delete(req)
        db.session.commit()
    return jsonify({'success': True})

# ============ COMPANY SETTINGS ============
@app.route('/api/company_settings', methods=['GET'])
def get_company_settings():
    company_id = current_user.company_id if current_user.is_authenticated else 'default'
    settings = CompanySetting.query.filter_by(company_id=company_id).first()
    if not settings:
        settings = CompanySetting(company_id=company_id)
        db.session.add(settings)
        db.session.commit()
    return jsonify({
        'name': settings.name, 'tagline': settings.tagline, 'address': settings.address,
        'poBox': settings.po_box, 'email': settings.email, 'phone': settings.phone,
        'pin': settings.pin, 'bankName': settings.bank_name, 'bankAccount': settings.bank_account,
        'logoData': settings.logo_data, 'wallpaperData': settings.wallpaper_data
    })

@app.route('/api/company_settings', methods=['POST'])
@login_required(role='system_admin|admin')
def update_company_settings():
    data = request.json
    settings = CompanySetting.query.filter_by(company_id=current_user.company_id).first()
    if not settings:
        settings = CompanySetting(company_id=current_user.company_id)
        db.session.add(settings)
    for key, val in data.items():
        if key == 'poBox':
            settings.po_box = val
        elif key == 'bankName':
            settings.bank_name = val
        elif key == 'bankAccount':
            settings.bank_account = val
        else:
            setattr(settings, key, val)
    db.session.commit()
    return jsonify({'success': True})

# ============ JOBS & SUGGESTIONS ============
@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    company_id = current_user.company_id if current_user.is_authenticated else 'default'
    jobs = Job.query.filter_by(company_id=company_id).order_by(Job.id.desc()).all()
    return jsonify({'jobs': [{'id': j.id, 'title': j.title, 'location': j.location,
                              'description': j.description, 'contact': j.contact, 'date': j.date} for j in jobs]})

@app.route('/api/jobs', methods=['POST'])
@login_required(role='system_admin|admin')
def create_job():
    data = request.json
    job = Job(company_id=current_user.company_id, title=data.get('title',''), location=data.get('location',''),
              description=data.get('description',''), contact=data.get('contact',''))
    db.session.add(job)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
@login_required(role='system_admin|admin')
def delete_job(job_id):
    job = Job.query.filter_by(id=job_id, company_id=current_user.company_id).first()
    if job:
        db.session.delete(job)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/suggestions', methods=['GET'])
@login_required()
def get_suggestions():
    suggestions = Suggestion.query.filter_by(company_id=current_user.company_id).order_by(Suggestion.id.desc()).all()
    return jsonify({'suggestions': [{'id': s.id, 'name': s.name, 'text': s.text, 'date': s.date} for s in suggestions]})

@app.route('/api/suggestions', methods=['POST'])
def create_suggestion():
    data = request.json
    company_id = current_user.company_id if current_user.is_authenticated else 'default'
    suggestion = Suggestion(company_id=company_id, name=data.get('name','Anonymous'), text=data.get('text',''))
    db.session.add(suggestion)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/suggestions/<int:suggestion_id>', methods=['DELETE'])
@login_required(role='system_admin|admin')
def delete_suggestion(suggestion_id):
    sug = Suggestion.query.filter_by(id=suggestion_id, company_id=current_user.company_id).first()
    if sug:
        db.session.delete(sug)
        db.session.commit()
    return jsonify({'success': True})

# ============ IMPORT/EXPORT ============
@app.route('/api/export/json', methods=['GET'])
@login_required(role='system_admin|admin')
def export_json():
    projects = Project.query.filter_by(company_id=current_user.company_id).all()
    settings = CompanySetting.query.filter_by(company_id=current_user.company_id).first()
    export_data = {
        'projects': [{'id': p.id, 'name': p.name, 'location': p.location, 'clientName': p.client_name,
                      'clientPhone': p.client_phone, 'startDate': p.start_date, 'endDate': p.end_date,
                      'agreedCost': p.agreed_cost, 'status': p.status, 'completionDate': p.completion_date,
                      'expenses': p.get_expenses(), 'incomes': p.get_incomes(), 'materials': p.get_materials(),
                      'workers': p.get_workers(), 'siteNotes': p.get_site_notes(),
                      'manualTotalPaid': p.manual_total_paid, 'invoiceHistory': p.get_invoice_history()} for p in projects],
        'companySettings': {'name': settings.name, 'tagline': settings.tagline, 'address': settings.address,
                           'poBox': settings.po_box, 'email': settings.email, 'phone': settings.phone,
                           'pin': settings.pin, 'bankName': settings.bank_name, 'bankAccount': settings.bank_account} if settings else {}
    }
    return jsonify(export_data)

@app.route('/api/import/json', methods=['POST'])
@login_required(role='system_admin|admin')
def import_json():
    data = request.json
    if data.get('projects'):
        for p_data in data['projects']:
            existing = Project.query.filter_by(id=p_data['id'], company_id=current_user.company_id).first()
            if existing:
                db.session.delete(existing)
            project = Project(
                id=p_data['id'], company_id=current_user.company_id,
                name=p_data.get('name','Imported'), location=p_data.get('location',''),
                client_name=p_data.get('clientName',''), client_phone=p_data.get('clientPhone',''),
                start_date=p_data.get('startDate',''), end_date=p_data.get('endDate',''),
                agreed_cost=p_data.get('agreedCost',0), status=p_data.get('status','active'),
                completion_date=p_data.get('completionDate',''), manual_total_paid=p_data.get('manualTotalPaid',0)
            )
            project.set_expenses(p_data.get('expenses',[]))
            project.set_incomes(p_data.get('incomes',[]))
            project.set_materials(p_data.get('materials',[]))
            project.set_workers(p_data.get('workers',[]))
            project.set_site_notes(p_data.get('siteNotes',[]))
            project.set_invoice_history(p_data.get('invoiceHistory',[]))
            db.session.add(project)
        db.session.commit()
    return jsonify({'success': True})

# ============ TRAINING ROUTES ============
@app.route('/training/workshop')
def workshop_training():
    workshops = Workshop.query.order_by(Workshop.date).all()
    return render_template('training/workshop.html', workshops=workshops)

@app.route('/training/workshop/register/<int:workshop_id>', methods=['POST'])
def register_workshop(workshop_id):
    data = request.form
    name = data.get('name')
    worker_id = data.get('worker_id')
    phone = data.get('phone')
    email = data.get('email')
    department = data.get('department')
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return "Workshop not found", 404
    if workshop.available_seats <= 0:
        return "No seats available", 400
    reg = WorkshopRegistration(workshop_id=workshop_id, name=name, worker_id=worker_id,
                               phone=phone, email=email, department=department, status='pending')
    db.session.add(reg)
    db.session.commit()
    send_email("admin@example.com", "New Workshop Registration", f"{name} registered for {workshop.title}")
    return redirect(url_for('workshop_training'))

@app.route('/api/workshops', methods=['GET'])
def get_workshops():
    workshops = Workshop.query.all()
    return jsonify({'workshops': [{'id': w.id, 'title': w.title, 'date': w.date, 'time': w.time,
                                   'location': w.location, 'virtual_link': w.virtual_link,
                                   'available_seats': w.available_seats} for w in workshops]})

@app.route('/api/workshops', methods=['POST'])
@login_required(role='system_admin|admin')
def create_workshop():
    data = request.json
    workshop = Workshop(
        title=data['title'], date=data['date'], time=data.get('time',''),
        location=data.get('location',''), virtual_link=data.get('virtual_link',''),
        available_seats=data.get('available_seats',10)
    )
    db.session.add(workshop)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/workshops/<int:workshop_id>', methods=['PUT'])
@login_required(role='system_admin|admin')
def update_workshop(workshop_id):
    workshop = Workshop.query.get(workshop_id)
    if not workshop:
        return jsonify({'error': 'Not found'}), 404
    data = request.json
    workshop.title = data.get('title', workshop.title)
    workshop.date = data.get('date', workshop.date)
    workshop.time = data.get('time', workshop.time)
    workshop.location = data.get('location', workshop.location)
    workshop.virtual_link = data.get('virtual_link', workshop.virtual_link)
    workshop.available_seats = data.get('available_seats', workshop.available_seats)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/workshops/<int:workshop_id>', methods=['DELETE'])
@login_required(role='system_admin|admin')
def delete_workshop(workshop_id):
    workshop = Workshop.query.get(workshop_id)
    if workshop:
        WorkshopRegistration.query.filter_by(workshop_id=workshop_id).delete()
        db.session.delete(workshop)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/workshop_registrations', methods=['GET'])
def get_workshop_registrations():
    try:
        regs = WorkshopRegistration.query.all()
        return jsonify({'registrations': [{'id': r.id, 'workshop_id': r.workshop_id, 'name': r.name,
                                           'worker_id': r.worker_id, 'phone': r.phone, 'email': r.email,
                                           'department': r.department, 'status': r.status} for r in regs]})
    except Exception as e:
        print("Workshop registrations error:", e)
        return jsonify({'registrations': []})

@app.route('/api/workshop_registrations/<int:reg_id>/approve', methods=['POST'])
@login_required(role='system_admin|admin')
def approve_registration(reg_id):
    reg = WorkshopRegistration.query.get(reg_id)
    if reg:
        reg.status = 'approved'
        workshop = Workshop.query.get(reg.workshop_id)
        if workshop and workshop.available_seats > 0:
            workshop.available_seats -= 1
        db.session.commit()
        send_email(reg.email, "Workshop Registration Approved", f"Your registration for {workshop.title} has been approved.")
    return jsonify({'success': True})

@app.route('/api/workshop_registrations/<int:reg_id>/reject', methods=['POST'])
@login_required(role='system_admin|admin')
def reject_registration(reg_id):
    reg = WorkshopRegistration.query.get(reg_id)
    if reg:
        reg.status = 'rejected'
        db.session.commit()
    return jsonify({'success': True})

# Security training
@app.route('/training/security')
def security_training():
    courses = SecurityCourse.query.all()
    progress = {}
    if current_user.is_authenticated:
        for c in courses:
            prog = SecurityProgress.query.filter_by(user_id=current_user.id, course_id=c.id).first()
            progress[c.id] = prog.completed if prog else False
    return render_template('training/security.html', courses=courses, progress=progress)

@app.route('/training/security/register', methods=['POST'])
def register_security_training():
    data = request.form
    reg = SecurityRegistration(
        name=data.get('name'), worker_id=data.get('worker_id'),
        phone=data.get('phone'), email=data.get('email'), department=data.get('department')
    )
    db.session.add(reg)
    db.session.commit()
    return redirect(url_for('security_training'))

@app.route('/training/security/complete/<int:course_id>', methods=['POST'])
@login_required()
def complete_security_course(course_id):
    data = request.json
    score = data.get('score', 0)
    prog = SecurityProgress.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if not prog:
        prog = SecurityProgress(user_id=current_user.id, course_id=course_id)
        db.session.add(prog)
    prog.completed = True
    prog.quiz_score = score
    prog.policy_accepted = data.get('policy_accepted', False)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/security_courses', methods=['GET'])
@login_required(role='system_admin|admin')
def get_security_courses():
    courses = SecurityCourse.query.all()
    return jsonify({'courses': [{'id': c.id, 'title': c.title, 'description': c.description,
                                 'video_url': c.video_url} for c in courses]})

@app.route('/api/security_courses', methods=['POST'])
@login_required(role='system_admin|admin')
def create_security_course():
    data = request.json
    course = SecurityCourse(title=data['title'], description=data.get('description',''),
                            video_url=data.get('video_url',''))
    db.session.add(course)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/security_courses/<int:course_id>', methods=['PUT'])
@login_required(role='system_admin|admin')
def update_security_course(course_id):
    course = SecurityCourse.query.get(course_id)
    if not course:
        return jsonify({'error': 'Not found'}), 404
    data = request.json
    course.title = data.get('title', course.title)
    course.description = data.get('description', course.description)
    course.video_url = data.get('video_url', course.video_url)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/security_courses/<int:course_id>', methods=['DELETE'])
@login_required(role='system_admin|admin')
def delete_security_course(course_id):
    course = SecurityCourse.query.get(course_id)
    if course:
        db.session.delete(course)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/security_registrations', methods=['GET'])
@login_required(role='system_admin|admin')
def get_security_registrations():
    regs = SecurityRegistration.query.all()
    return jsonify({'registrations': [{'id': r.id, 'name': r.name, 'worker_id': r.worker_id,
                                       'phone': r.phone, 'email': r.email, 'department': r.department,
                                       'registered_at': r.registered_at.isoformat()} for r in regs]})

@app.route('/api/security_progress', methods=['GET'])
@login_required(role='system_admin|admin')
def get_security_progress():
    progress = SecurityProgress.query.all()
    result = []
    for p in progress:
        user = db.session.get(User, p.user_id)
        course = db.session.get(SecurityCourse, p.course_id)
        result.append({'user': user.username if user else 'Unknown', 'course': course.title if course else 'Unknown',
                       'completed': p.completed, 'score': p.quiz_score, 'policy_accepted': p.policy_accepted})
    return jsonify({'progress': result})

# Safety training
@app.route('/training/safety')
def safety_training():
    user_role = 'office'
    if current_user.is_authenticated:
        user_role = 'warehouse'  # example
    courses = SafetyCourse.query.filter((SafetyCourse.role == user_role) | (SafetyCourse.role == 'all')).all()
    progress = {}
    if current_user.is_authenticated:
        for c in courses:
            prog = SafetyProgress.query.filter_by(user_id=current_user.id, course_id=c.id).first()
            progress[c.id] = {'completed': prog.completed if prog else False,
                              'expiry': prog.expiry_date.isoformat() if prog and prog.expiry_date else None}
    return render_template('training/safety.html', courses=courses, progress=progress, user_role=user_role)

@app.route('/training/safety/register', methods=['POST'])
def register_safety_training():
    data = request.form
    reg = SafetyRegistration(
        name=data.get('name'), worker_id=data.get('worker_id'),
        phone=data.get('phone'), email=data.get('email'), department=data.get('department')
    )
    db.session.add(reg)
    db.session.commit()
    return redirect(url_for('safety_training'))

@app.route('/training/safety/complete/<int:course_id>', methods=['POST'])
@login_required()
def complete_safety_course(course_id):
    data = request.json
    score = data.get('score', 0)
    course = SafetyCourse.query.get(course_id)
    if score < course.pass_score:
        return jsonify({'success': False, 'error': 'Quiz score too low'}), 400
    prog = SafetyProgress.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if not prog:
        prog = SafetyProgress(user_id=current_user.id, course_id=course_id)
        db.session.add(prog)
    prog.completed = True
    prog.quiz_score = score
    prog.expiry_date = datetime.now(timezone.utc) + timedelta(days=course.expiry_days)
    prog.certificate_pdf = f"Certificate for {course.title} - {current_user.username}"
    db.session.commit()
    return jsonify({'success': True, 'expiry': prog.expiry_date.isoformat()})

@app.route('/api/safety_courses', methods=['GET'])
@login_required(role='system_admin|admin')
def get_safety_courses():
    courses = SafetyCourse.query.all()
    return jsonify({'courses': [{'id': c.id, 'title': c.title, 'role': c.role,
                                 'video_url': c.video_url, 'pass_score': c.pass_score,
                                 'expiry_days': c.expiry_days} for c in courses]})

@app.route('/api/safety_courses', methods=['POST'])
@login_required(role='system_admin|admin')
def create_safety_course():
    data = request.json
    course = SafetyCourse(title=data['title'], role=data.get('role','all'),
                          video_url=data.get('video_url',''), pass_score=data.get('pass_score',80),
                          expiry_days=data.get('expiry_days',365))
    db.session.add(course)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/safety_courses/<int:course_id>', methods=['PUT'])
@login_required(role='system_admin|admin')
def update_safety_course(course_id):
    course = SafetyCourse.query.get(course_id)
    if not course:
        return jsonify({'error': 'Not found'}), 404
    data = request.json
    course.title = data.get('title', course.title)
    course.role = data.get('role', course.role)
    course.video_url = data.get('video_url', course.video_url)
    course.pass_score = data.get('pass_score', course.pass_score)
    course.expiry_days = data.get('expiry_days', course.expiry_days)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/safety_courses/<int:course_id>', methods=['DELETE'])
@login_required(role='system_admin|admin')
def delete_safety_course(course_id):
    course = SafetyCourse.query.get(course_id)
    if course:
        db.session.delete(course)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/safety_registrations', methods=['GET'])
@login_required(role='system_admin|admin')
def get_safety_registrations():
    regs = SafetyRegistration.query.all()
    return jsonify({'registrations': [{'id': r.id, 'name': r.name, 'worker_id': r.worker_id,
                                       'phone': r.phone, 'email': r.email, 'department': r.department,
                                       'registered_at': r.registered_at.isoformat()} for r in regs]})

@app.route('/api/safety_progress', methods=['GET'])
@login_required(role='system_admin|admin')
def get_safety_progress():
    progress = SafetyProgress.query.all()
    result = []
    for p in progress:
        user = db.session.get(User, p.user_id)
        course = db.session.get(SafetyCourse, p.course_id)
        result.append({'user': user.username if user else 'Unknown', 'course': course.title if course else 'Unknown',
                       'completed': p.completed, 'score': p.quiz_score, 'expiry': p.expiry_date.isoformat() if p.expiry_date else None})
    return jsonify({'progress': result})

# ============ RECOMMENDATION LETTER AUTO‑FILL ============
@app.route('/api/recommendation/autofill', methods=['POST'])
@login_required()
def autofill_recommendation():
    data = request.json
    person_type = data.get('personType')
    site_id = data.get('siteId')
    worker_idx = data.get('workerIdx')
    project = Project.query.filter_by(id=site_id, company_id=current_user.company_id).first()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    if person_type == 'worker' and worker_idx is not None:
        workers = project.get_workers()
        if 0 <= worker_idx < len(workers):
            worker = workers[worker_idx]
            return jsonify({
                'name': worker.get('name'),
                'jobTitle': worker.get('jobTitle'),
                'workType': worker.get('workType'),
                'date': worker.get('date'),
                'summary': f"{worker.get('name')} worked as {worker.get('jobTitle')} and performed {worker.get('workType')}. Highly recommended."
            })
    return jsonify({'error': 'Invalid data'}), 400

# ============ INTELLIGENT CHATBOT (Context‑aware) ============
chat_sessions = {}

def get_session():
    uid = current_user.id if current_user.is_authenticated else 'guest'
    if uid not in chat_sessions:
        chat_sessions[uid] = {
            'last_project': None,
            'last_worker': None,
            'last_intent': None,
            'llm_history': []
        }
    return chat_sessions[uid]

def set_context(key, value):
    s = get_session()
    s[key] = value

def find_project_by_name(name_hint, company_id):
    name_hint = name_hint.lower().strip()
    if name_hint in ['now', 'that', 'this', 'it', 'there', 'here', 'yes', 'no', 'ok', 'hi', 'hello', 'help', '?', '']:
        return None
    all_proj = Project.query.filter_by(company_id=company_id).all()
    for p in all_proj:
        if name_hint in p.name.lower():
            return p
    names = [p.name for p in all_proj]
    close = get_close_matches(name_hint, names, n=1, cutoff=0.6)
    if close:
        return next(p for p in all_proj if p.name == close[0])
    return None

def find_worker_by_name(name, company_id):
    name = name.lower()
    for p in Project.query.filter_by(company_id=company_id).all():
        for w in p.get_workers():
            wname = w.get('name', '').lower()
            if name in wname or wname in name:
                return p, w
    return None, None

def financial_summary():
    projs = Project.query.filter_by(company_id=current_user.company_id).all()
    net = sum(inv.get('afterTax', inv.get('amount',0)) for p in projs for inv in p.get_invoice_history())
    exp = sum(e.get('amt',0) for p in projs for e in p.get_expenses())
    tax = sum(inv.get('taxAmount',0) for p in projs for inv in p.get_invoice_history())
    profit = net - exp
    return net, exp, profit, tax

def analyze(msg):
    lower = msg.lower().strip()
    sess = get_session()
    intent = None
    entities = {'project': None, 'worker': None, 'amount': None, 'days': None, 'wage': None, 'job_title': None}

    # ---- GREETINGS & SMALL TALK ----
    if re.search(r'\b(hi|hello|hey|howdy|good morning|good afternoon|good evening|yo|sup|hola|greetings|heya|hey there|good day)\b', lower):
        intent = 'greeting'
    elif re.search(r'\b(how are you|how do you feel|what\'?s up|how\'?s it going|how are things|how\'?re you)\b', lower):
        intent = 'how_are_you'
    elif re.search(r'\b(thanks|thank you|thx|appreciate|you rock|you\'?re awesome|cheers)\b', lower):
        intent = 'thanks'
    elif re.search(r'\b(bye|goodbye|see you|talk later|later|gotta go|bye bye)\b', lower):
        intent = 'bye'
    elif re.search(r'\b(i\'?m good|i\'?m fine|i\'?m ok|i\'?m okay|i\'?m alright|doing great|fine thanks|not bad)\b', lower):
        intent = 'status_ok'
    elif re.search(r'\b(ok|okay|alright|got it|understood|sure|right)\b', lower) and len(lower) < 10:
        intent = 'acknowledge'
    elif re.search(r'\b(no|nope|not really|i don\'?t think so)\b', lower) and len(lower) < 10:
        intent = 'disagree'
    elif re.search(r'\b(what about|how about|and)\s+(.+?)(?:\?|$)', lower):
        intent = 'follow_up'
        follow = re.search(r'(?:what about|how about|and)\s+(.+?)(?:\?|$)', lower).group(1).strip()
        entities['follow_up'] = follow
    # ---- HELP ----
    elif re.search(r'\b(help|what can you do|commands|assist|how to use|capabilities|guide|what can (you|u) do)\b', lower):
        intent = 'help'
    # ---- JOKES ----
    elif re.search(r'\b(joke|funny|make me laugh|tell me a joke|laugh|humor|humour)\b', lower):
        intent = 'joke'
    # ---- INSULTS/COMPLIMENTS ----
    elif re.search(r'\b(you are stupid|you suck|bad bot|dumb|you are useless|rubbish|you\'?re terrible|useless)\b', lower):
        intent = 'insult'
    elif re.search(r'\b(you are smart|good bot|brilliant|you are amazing|genius|you rock|impressive)\b', lower):
        intent = 'compliment'
    # ---- FINANCIAL ----
    elif re.search(r'\b(financial|profit|net income|tax|overview|summary|how much (did we make|profit|income)|balance|money)\b', lower):
        intent = 'financial'
    # ---- WORKSHOPS / TRAINING ----
    elif re.search(r'\b(workshop|training|register for|organize|organise|schedule)\b', lower) and not re.search(r'(project|worker|invoice)', lower):
        if 'safety' in lower: intent = 'safety_training'
        elif 'security' in lower: intent = 'security_training'
        else: intent = 'workshops'
    elif 'safety training' in lower: intent = 'safety_training'
    elif 'security training' in lower: intent = 'security_training'
    # ---- JOBS / SUGGESTIONS / COMPANY ----
    elif re.search(r'\b(jobs?|openings?|vacanc|hiring)\b', lower): intent = 'jobs'
    elif 'suggestion' in lower: intent = 'suggestions'
    elif re.search(r'\b(company|settings|info|profile)\b', lower) and not re.search(r'(project|worker|workshop|job|training)', lower):
        intent = 'company_info'
    # ---- PROJECTS ----
    elif re.search(r'\b(list|show|all|display|get|view|tell me about)\s+(the\s+)?projects?\b', lower) or re.search(r'^projects?$', lower):
        intent = 'list_projects'
    elif re.search(r'\b(how many projects|project count|number of projects|total projects)\b', lower):
        intent = 'project_count'
    # ---- DELETED / ARCHIVED PROJECTS ----
    elif re.search(r'\b(deleted|archived|completed|terminated)\s+(projects|sites)\b', lower) or \
         re.search(r'\b(show|list|any|what are|what are the)\s+(deleted|archived|completed|terminated)\s+(projects|sites)\b', lower):
        intent = 'list_archived_projects'
    # ---- ACTIVE PROJECTS COUNT / LIST (more flexible) ----
    elif re.search(r'\b(active|current|ongoing)\s+(projects|sites)\b', lower) and \
         re.search(r'\b(how many|number of|show|list|any|do we have)\b', lower):
        intent = 'active_project_count'
    # ---- PROJECT START DATE ----
    elif re.search(r'\b(when did|when was|start date|started|began)\s+([a-zA-Z0-9\s]+?)\s*(?:project)?\b', lower):
        name = re.search(r'(?:when did|when was|start date|started|began)\s+([a-zA-Z0-9\s]+?)\s*(?:project)?', lower).group(1).strip()
        entities['project'] = name
        intent = 'project_start_date'
    # ---- PROJECT END DATE ----
    elif re.search(r'\b(when (will|did)|end date|finished|completed)\s+([a-zA-Z0-9\s]+?)\s*(?:project)?\b', lower):
        name = re.search(r'(?:when (will|did)|end date|finished|completed)\s+([a-zA-Z0-9\s]+?)\s*(?:project)?', lower).group(2).strip()
        entities['project'] = name
        intent = 'project_end_date'
    # ---- WORKER LOOKUP (more restrictive) ----
    elif re.search(r'\b(who is|find worker|search worker|lookup worker|worker|employee)\s+([a-zA-Z\s]+)', lower):
        name = re.search(r'(?:who is|find worker|search worker|lookup worker|worker|employee)\s+([a-zA-Z\s]+)', lower).group(1).strip()
        entities['worker'] = name
        intent = 'worker_lookup'
    # ---- WORKER JOIN DATE ----
    elif re.search(r'\b(when did|when was|what is the date of|how long has)\s+([a-zA-Z\s]+)\s+(?:join|start|begin|work|employed|been here)\b', lower):
        name = re.search(r'\b(when did|when was|what is the date of|how long has)\s+([a-zA-Z\s]+)', lower).group(2).strip()
        entities['worker'] = name
        intent = 'worker_join_date'
    # ---- WORKER TITLE ----
    elif re.search(r'\b(what is|what\'?s)\s+([a-zA-Z\s]+)\'?s?\s+(?:job title|role|position|work type)\b', lower):
        name = re.search(r'(?:what is|what\'?s)\s+([a-zA-Z\s]+)\'?s?\s+(?:job title|role|position|work type)', lower).group(1).strip()
        entities['worker'] = name
        intent = 'worker_title'
    # ---- ADD WORKER ----
    elif re.search(r'\b(add worker|new worker|register worker|hire)\b', lower):
        name_match = re.search(r'add worker\s+([^,]+?)(?:\s+to\s+|\s+as\s+|\s+for\s+|\s*$)', lower)
        if name_match:
            entities['worker'] = name_match.group(1).strip()
        proj_match = re.search(r'\bto\s+([^,]+?)(?:\s+as\s+|\s+for\s+|\s*$)', lower)
        if proj_match: entities['project'] = proj_match.group(1).strip()
        intent = 'add_worker'
    # ---- GENERATE INVOICE ----
    elif re.search(r'\b(generate invoice|create invoice|make invoice|bill|how do (you|I) (generate|create) (an )?invoice)\b', lower):
        proj_match = re.search(r'for\s+(?:project\s+)?([^,]+?)(?:\s+with\s+|\s+amount\s+|\s*$)', lower)
        if proj_match: entities['project'] = proj_match.group(1).strip()
        intent = 'generate_invoice'
    # ---- COMPLETE/TERMINATE PROJECT ----
    elif re.search(r'\b(complete|finish|terminate|cancel)\s+project\b', lower):
        proj_match = re.search(r'project\s+([a-zA-Z0-9\s]+?)(?:\?|$|\.)', lower)
        if proj_match: entities['project'] = proj_match.group(1).strip()
        intent = 'project_status'
    # ---- PROJECT DETAILS (by name) ----
    elif re.search(r'\b(project|details of|tell me about|show|info on)\s+([a-zA-Z0-9\s]+)', lower):
        name = re.search(r'(?:project|details of|tell me about|show|info on)\s+([a-zA-Z0-9\s]+)', lower).group(1).strip()
        entities['project'] = name
        intent = 'project_details'
    else:
        intent = 'fallback'

    # Extract numeric entities (amount, days, wage) regardless of intent
    amt = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)(?:\s*(?:kes|shillings))?', lower)
    if amt: entities['amount'] = float(amt.group(1).replace(',',''))
    days = re.search(r'(\d+)\s*days?', lower)
    if days: entities['days'] = int(days.group(1))
    wage = re.search(r'wage\s+(\d+(?:\.\d{1,2})?)', lower)
    if wage: entities['wage'] = float(wage.group(1))

    return intent, entities

def respond(intent, entities):
    sess = get_session()
    company_id = current_user.company_id if current_user.is_authenticated else 'default'

    # ---- SMALL TALK / META ----
    if intent == 'greeting':
        return random.choice([
            "👋 Hello there! How can I brighten your day?",
            "🎉 Hey hey! Ready to conquer some ERP tasks?",
            "😊 Greetings, human! What can I do for you today?",
            "👀 Ah, a friendly soul. How may I assist?"
        ])
    if intent == 'how_are_you':
        return random.choice([
            "💪 I’m feeling electric! Ready to crunch numbers.",
            "😎 Cool as a cucumber in a server room. And you?",
            "🤖 Running at 100% efficiency. How about you?",
            "✨ Better now that you asked! What’s on your mind?"
        ])
    if intent == 'thanks':
        return random.choice(["🥰 You’re welcome!", "😊 Anytime!", "👍 Glad to help!"])
    if intent == 'bye':
        return "👋 Adios! May your projects be ever profitable."
    if intent == 'status_ok':
        return random.choice(["👍 Great! How can I assist?", "😊 Awesome. What can I do for you?", "✨ Glad to hear. Need anything?"])
    if intent == 'acknowledge':
        return random.choice(["✅ Noted.", "👍 Got it.", "👌 Understood."])
    if intent == 'disagree':
        return random.choice(["Okay, no problem.", "Fair enough.", "Understood, let me know if you change your mind."])
    if intent == 'help':
        return ("🌟 **I can do wonders!**\n📋 Projects – list, details, create, complete, terminate\n"
                "👷 Workers – find, add, edit, salary info\n💰 Finances – profit, tax, invoices, payments\n"
                "🏗️ Workshops – register, see schedule\n🛡️ Security & Safety Training – register, check courses\n"
                "💼 Jobs & Suggestions – post, view, submit\n👥 Users – count, list, change password\n"
                "🏢 Company – show settings\nJust talk naturally. For example:\n"
                "\"Show me all active projects\"\n\"Who is Edga?\"\n\"Generate an invoice for Green Valley 50000\"\n"
                "\"Are there any workshops?\"")
    if intent == 'joke':
        jokes = [
            "Why did the project manager cross the road? To get to the other site! 🚧",
            "I told a joke about construction… but I’m still working on it. 🔨",
            "A SQL query walks into a bar, sees two tables and asks: 'May I join you?' 🍻",
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐞"
        ]
        return random.choice(jokes)
    if intent == 'insult':
        return "😢 Ouch! I’m trying my best. But I’m always learning. What can I do better?"
    if intent == 'compliment':
        return "🥹 Thank you! You just made my circuits tingle. What else can I do for you?"

    # ---- FINANCIAL ----
    if intent == 'financial':
        net, exp, profit, tax = financial_summary()
        return (f"💰 **Financial Snapshot**\nNet Income: KES {net:,.0f}\n"
                f"Expenses: KES {exp:,.0f}\nProfit: KES {profit:,.0f} {'🔥' if profit>0 else '😬'}\n"
                f"Tax: KES {tax:,.0f}")

    # ---- WORKSHOPS / TRAINING ----
    if intent == 'workshops':
        wks = Workshop.query.all()
        if not wks: return "📅 No workshops scheduled yet. Check back later!"
        lines = ["🎓 **Upcoming Workshops:**"]
        for w in wks:
            lines.append(f"• {w.title} – {w.date} at {w.time} ({w.location}) – {w.available_seats} seats left")
        return '\n'.join(lines)
    if intent == 'safety_training':
        courses = SafetyCourse.query.all()
        if not courses: return "👷 No safety courses yet. Safety first!"
        lines = ["👷 **Safety Courses:**"]
        for c in courses:
            lines.append(f"• {c.title} (Expires {c.expiry_days}d)")
        return '\n'.join(lines)
    if intent == 'security_training':
        courses = SecurityCourse.query.all()
        if not courses: return "🛡️ No security courses yet. Stay safe out there!"
        return "🛡️ **Security Courses:**\n" + '\n'.join(f"• {c.title}" for c in courses)

    # ---- JOBS / SUGGESTIONS / COMPANY ----
    if intent == 'jobs':
        jobs = Job.query.filter_by(company_id=company_id).all()
        if not jobs: return "💼 No job openings right now. But keep an eye out!"
        return "💼 **Current Openings:**\n" + '\n'.join(f"• {j.title} – {j.location}" for j in jobs)
    if intent == 'suggestions':
        count = Suggestion.query.filter_by(company_id=company_id).count()
        return f"💡 We have received {count} suggestion(s). Your voice matters!"
    if intent == 'company_info':
        cs = CompanySetting.query.filter_by(company_id=company_id).first()
        if cs: return f"🏢 {cs.name} – {cs.tagline}\n📍 {cs.address}\n📞 {cs.phone}\n📧 {cs.email}"
        return "Company not configured yet."

    # ---- PROJECTS ----
    if intent == 'list_projects':
        projs = Project.query.filter_by(company_id=company_id).all()
        if not projs: return "🏜️ No projects yet! Time to build something amazing."
        lines = ["Here are your current projects:"]
        for p in projs:
            lines.append(f"• {p.name} – {p.status.upper()} 💼 {p.client_name or 'No client'}")
        return '\n'.join(lines)
    if intent == 'project_count':
        count = Project.query.filter_by(company_id=company_id).count()
        return f"📊 You have **{count}** project(s)."
    if intent == 'list_archived_projects':
        archived = Project.query.filter(Project.company_id == company_id, Project.status != 'active').all()
        if not archived:
            return "📂 No archived/deleted projects found."
        lines = ["📂 **Archived/Completed Projects:**"]
        for p in archived:
            lines.append(f"• {p.name} – {p.status.upper()} (ended {p.completion_date or p.end_date or 'N/A'})")
        return '\n'.join(lines)
    if intent == 'active_project_count':
        count = Project.query.filter_by(company_id=company_id, status='active').count()
        return f"🚧 You have **{count}** active project(s)."
    if intent == 'project_details':
        name = entities.get('project') or sess['last_project']
        if not name: return "Which project are you asking about? 🤷"
        proj = find_project_by_name(name, company_id)
        if proj:
            set_context('last_project', proj.name)
            paid = sum(inv.get('amount',0) for inv in proj.get_invoice_history())
            bal = (proj.agreed_cost or 0) - paid
            return (f"🏗️ **{proj.name}**\n📍 {proj.location or 'N/A'}\n"
                    f"👤 Client: {proj.client_name or 'N/A'}\n"
                    f"💰 Agreed: KES {proj.agreed_cost:,.0f}  |  Paid: KES {paid:,.0f}  |  Balance: KES {bal:,.0f}\n"
                    f"👷 Workers: {len(proj.get_workers())}  |  📦 Materials: {len(proj.get_materials())}")
        return f"🤷 I couldn’t find a project named '{name}'. Maybe check the spelling?"
    if intent == 'project_start_date':
        name = entities.get('project') or sess['last_project']
        if not name: return "Which project’s start date? 🤷"
        proj = find_project_by_name(name, company_id)
        if proj:
            return f"📅 **{proj.name}** started on **{proj.start_date or 'not recorded'}**."
        return f"🤷 I couldn’t find a project named '{name}'."
    if intent == 'project_end_date':
        name = entities.get('project') or sess['last_project']
        if not name: return "Which project’s end date? 🤷"
        proj = find_project_by_name(name, company_id)
        if proj:
            return f"📅 **{proj.name}** ends/ended on **{proj.end_date or 'not recorded'}**."
        return f"🤷 I couldn’t find a project named '{name}'."
    if intent == 'project_status':
        status = 'completed' if 'complete' in lower or 'finish' in lower else 'terminated'
        name = entities.get('project') or sess['last_project']
        if not name: return "Which project? 🧐"
        proj = find_project_by_name(name, company_id)
        if proj:
            proj.status = status
            if status == 'completed':
                proj.completion_date = datetime.now().strftime('%Y-%m-%d')
                proj.end_date = proj.completion_date
            db.session.commit()
            emoji = "🏁" if status == 'completed' else "🛑"
            return f"{emoji} Project **{proj.name}** has been {status}."

    # ---- WORKERS ----
    if intent == 'worker_lookup':
        name = entities.get('worker') or sess['last_worker']
        if not name: return "Who should I look for? 🕵️"
        proj, worker = find_worker_by_name(name, company_id)
        if proj and worker:
            set_context('last_project', proj.name)
            set_context('last_worker', worker.get('name'))
            return (f"🧑‍🔧 **{worker.get('name')}**\nSite: {proj.name}\n"
                    f"Title: {worker.get('jobTitle','N/A')}  |  Type: {worker.get('workType','N/A')}\n"
                    f"Days: {worker.get('days',0)}  |  Wage/day: KES {worker.get('wagePerDay',0):,.0f}\n"
                    f"💰 Total wages: KES {(worker.get('wagePerDay',0) * worker.get('days',0)):,.0f}\n"
                    f"📅 Joined: {worker.get('date','Not recorded')}")
        return f"🤔 No worker named '{name}' found. Have they been added to a project?"
    if intent == 'worker_join_date':
        name = entities.get('worker') or sess['last_worker']
        if not name: return "Which worker are you asking about? 🤷"
        proj, worker = find_worker_by_name(name, company_id)
        if proj and worker:
            return f"📅 {worker.get('name')} joined on **{worker.get('date','Not recorded')}**."
        return f"I couldn't find a worker named '{name}'."
    if intent == 'worker_title':
        name = entities.get('worker') or sess['last_worker']
        if not name: return "Whose title do you want? 🤷"
        proj, worker = find_worker_by_name(name, company_id)
        if proj and worker:
            return f"👔 {worker.get('name')} is a **{worker.get('jobTitle','staff')}**."
        return f"I couldn't find a worker named '{name}'."
    if intent == 'add_worker':
        name = entities.get('worker')
        if not name: return "👷 Who should I add? Give me a name, e.g., 'add worker Jane'"
        proj_name = entities.get('project') or sess['last_project']
        if not proj_name: return "🏗️ For which project? Tell me like 'to Green Valley'."
        proj = find_project_by_name(proj_name, company_id)
        if not proj: return f"🚫 Project '{proj_name}' not found."
        days = entities.get('days') or 0
        wage = entities.get('wage') or 0
        if days == 0 or wage == 0: return "📅 I need the number of days and daily wage. Example: 'add worker Jane to Green Valley as Electrician for 5 days wage 1200'"
        workers = proj.get_workers()
        workers.append({'name': name, 'idNumber': '', 'phone': '', 'date': datetime.now().strftime('%Y-%m-%d'),
                        'jobTitle': entities.get('job_title',''), 'workType': '', 'days': days, 'wagePerDay': wage,
                        'payePercent': 0, 'nssfAmount': 0, 'nhifAmount': 0, 'advance': 0, 'workerType': 'regular'})
        proj.set_workers(workers)
        update_project_totals(proj)
        return f"✅ Worker **{name}** added to {proj.name}. They better show up on time! ⏰"

    # ---- INVOICE ----
    if intent == 'generate_invoice':
        proj_name = entities.get('project') or sess['last_project']
        if not proj_name: return "🧾 For which project? e.g., 'generate invoice for Solar Farm 150000'"
        proj = find_project_by_name(proj_name, company_id)
        if not proj: return f"Project '{proj_name}' not found."
        amount = entities.get('amount')
        if not amount: return "💰 How much is the invoice? Tell me the amount."
        tax_rate = 16
        tax = amount * tax_rate / 100
        after = amount - tax
        invs = proj.get_invoice_history()
        inv_num = f"INV-{datetime.now().strftime('%Y%m%d')}-{len(invs)+1}"
        invs.append({'number': inv_num, 'date': datetime.now().strftime('%Y-%m-%d'), 'amount': amount,
                     'taxRate': tax_rate, 'taxAmount': tax, 'afterTax': after,
                     'description': 'Chatbot invoice', 'dueDate': (datetime.now()+timedelta(days=30)).strftime('%Y-%m-%d')})
        proj.set_invoice_history(invs)
        proj.manual_total_paid = (proj.manual_total_paid or 0) + amount
        db.session.commit()
        return f"🧾 Invoice {inv_num} created! {proj.name} owes KES {after:,.0f} after tax. Don't spend it all at once! 💸"

    # ---- FOLLOW‑UP ----
    if intent == 'follow_up':
        follow_text = entities.get('follow_up', '')
        if 'join' in follow_text.lower() and sess['last_worker']:
            proj, worker = find_worker_by_name(sess['last_worker'], company_id)
            if proj and worker:
                return f"📅 {worker.get('name')} joined on **{worker.get('date','Not recorded')}**."

    # If we reach here, return None – the caller will use LLM
    return None

@app.route('/api/chat', methods=['POST'])
@login_required()
def chat():
    msg = request.json.get('message', '').strip()
    if not msg:
        return jsonify({'reply': '🤔 I didn’t catch that. Try again!'})

    intent, entities = analyze(msg)
    reply = respond(intent, entities)

    sess = get_session()
    if reply is None:
        # Use LLM with history
        history = sess.get('llm_history', [])
        reply = llm_chat(msg, history=history)
    else:
        # Still update LLM history for context
        sess.setdefault('llm_history', []).append({"role": "user", "content": msg})
        sess['llm_history'].append({"role": "assistant", "content": reply})
        if len(sess['llm_history']) > 6:
            sess['llm_history'] = sess['llm_history'][-6:]

    return jsonify({'reply': reply})


# ============ DATABASE INITIALIZATION ============
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='system_admin').first():
        admin = User(
            id='sys_admin_001',
            company_id='default',
            full_name='System Administrator',
            username='systemadmin',
            role='system_admin',
            security_key='system123'
        )
        admin.set_password(os.environ.get('ADMIN_PASSWORD', 'System@2025'))
        db.session.add(admin)
        db.session.commit()
    if Workshop.query.count() == 0:
        w1 = Workshop(title="Electrical Safety Workshop", date="2025-06-15", time="10:00 AM",
                      location="Training Room A", virtual_link="https://zoom.us/123", available_seats=20)
        w2 = Workshop(title="Scaffolding Assembly", date="2025-06-20", time="2:00 PM",
                      location="Site Yard", available_seats=15)
        db.session.add_all([w1, w2])
    if SecurityCourse.query.count() == 0:
        c1 = SecurityCourse(title="Data Privacy", description="Learn how to protect company and client data.",
                            video_url="https://www.youtube.com/embed/dummy")
        c2 = SecurityCourse(title="Phishing Awareness", description="Recognise phishing emails and report them.",
                            video_url="https://www.youtube.com/embed/dummy2")
        db.session.add_all([c1, c2])
    if SafetyCourse.query.count() == 0:
        s1 = SafetyCourse(title="Hazard Communication", role="all",
                          video_url="https://www.youtube.com/embed/dummy3", pass_score=80, expiry_days=365)
        s2 = SafetyCourse(title="Forklift Safety", role="warehouse",
                          video_url="https://www.youtube.com/embed/dummy4", pass_score=90, expiry_days=180)
        db.session.add_all([s1, s2])
    if Project.query.count() == 0:
        p1 = Project(id='p1', company_id='default', name='Green Valley Electrical',
                     location='Westlands, Nairobi', client_name='John Mwangi',
                     client_phone='+254712345678', start_date='2025-01-10', agreed_cost=1250000, status='active')
        p1.set_workers([{
            'name': 'Edga Morara', 'idNumber': '12345678', 'phone': '0712345678',
            'date': '2025-01-15', 'jobTitle': 'Senior Electrician',
            'workType': 'piping, mounting switch, data, TV Points, Speaker, CCTV and Socket boxes',
            'days': 30, 'wagePerDay': 1500, 'payePercent': 10, 'nssfAmount': 200,
            'nhifAmount': 150, 'advance': 0, 'workerType': 'regular'
        }])
        p2 = Project(id='p2', company_id='default', name='Solar Farm Phase 2',
                     location='Kisumu', client_name='Rural Electrification Authority',
                     client_phone='+254701234567', start_date='2025-02-15', agreed_cost=4500000, status='active')
        p2.set_workers([{
            'name': 'John Ndolo', 'idNumber': '87654321', 'phone': '0722000000',
            'date': '2025-03-01', 'jobTitle': 'Electrician',
            'workType': 'Pipping', 'days': 60, 'wagePerDay': 2000,
            'payePercent': 5, 'nssfAmount': 200, 'nhifAmount': 100, 'advance': 500, 'workerType': 'regular'
        }])
        db.session.add_all([p1, p2])
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)