from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import uuid
import json
import secrets
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///erp_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# ============ Database Models ============
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('company_id', 'username', name='unique_company_username'),)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_assigned_sites(self):
        return json.loads(self.assigned_site_ids) if self.assigned_site_ids else []
    
    def set_assigned_sites(self, site_ids):
        self.assigned_site_ids = json.dumps(site_ids)
    
    def get_id(self):
        return str(self.id)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    timestamp = db.Column(db.Float, default=lambda: datetime.utcnow().timestamp())
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
    date = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())

class Suggestion(db.Model):
    __tablename__ = 'suggestions'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), default='default')
    name = db.Column(db.String(100), default='Anonymous')
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(50), default=lambda: datetime.utcnow().isoformat())

# ============ TRAINING MODULE 1: WORKSHOP ============
class Workshop(db.Model):
    __tablename__ = 'workshops'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(50))
    location = db.Column(db.String(200))
    virtual_link = db.Column(db.String(500))
    available_seats = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============ TRAINING MODULE 2: SECURITY ============
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
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class SecurityRegistration(db.Model):
    __tablename__ = 'security_registrations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    worker_id = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============ TRAINING MODULE 3: SAFETY ============
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SafetyRegistration(db.Model):
    __tablename__ = 'safety_registrations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    worker_id = db.Column(db.String(50))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============ Helper Functions ============
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
    # Placeholder – replace with real email (Flask-Mail, SMTP, etc.)
    print(f"EMAIL TO {to}: {subject} - {body}")

# ============ Main Routes ============
@app.route('/')
def index():
    return render_template('index.html')

# ---------- Authentication API ----------
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
            expires_at=(datetime.utcnow() + timedelta(minutes=5)).timestamp()
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

# ---------- Projects API ----------
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
    # Use the setter methods for JSON fields to convert lists to JSON strings
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
    # Simple fields
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

# ---------- User Management API ----------
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

# ---------- Pending Admin Requests ----------
@app.route('/api/pending_requests', methods=['GET'])
@login_required(role='system_admin')
def get_pending_requests():
    now = datetime.utcnow().timestamp()
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

# ---------- Company Settings ----------
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

# ---------- Jobs & Suggestions ----------
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

# ---------- Data Import/Export ----------
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
# ---------- Workshop (Public and Admin) ----------
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

# Workshop Admin API
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
    regs = WorkshopRegistration.query.all()
    return jsonify({'registrations': [{'id': r.id, 'workshop_id': r.workshop_id, 'name': r.name,
                                       'worker_id': r.worker_id, 'phone': r.phone, 'email': r.email,
                                       'department': r.department, 'status': r.status} for r in regs]})

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

# ---------- Security Training ----------
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

# Security Admin API
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
        user = User.query.get(p.user_id)
        course = SecurityCourse.query.get(p.course_id)
        result.append({'user': user.username if user else 'Unknown', 'course': course.title if course else 'Unknown',
                       'completed': p.completed, 'score': p.quiz_score, 'policy_accepted': p.policy_accepted})
    return jsonify({'progress': result})

# ---------- Safety Training ----------
@app.route('/training/safety')
def safety_training():
    user_role = 'office'  # in real app, fetch from user profile
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
    prog.expiry_date = datetime.utcnow() + timedelta(days=course.expiry_days)
    prog.certificate_pdf = f"Certificate for {course.title} - {current_user.username}"
    db.session.commit()
    return jsonify({'success': True, 'expiry': prog.expiry_date.isoformat()})

# Safety Admin API
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
        user = User.query.get(p.user_id)
        course = SafetyCourse.query.get(p.course_id)
        result.append({'user': user.username if user else 'Unknown', 'course': course.title if course else 'Unknown',
                       'completed': p.completed, 'score': p.quiz_score, 'expiry': p.expiry_date.isoformat() if p.expiry_date else None})
    return jsonify({'progress': result})

# ============ Database Migration for worker_id ============
def add_missing_columns():
    """Add worker_id column to workshop_registrations if it doesn't exist."""
    conn = sqlite3.connect('erp_system.db')
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(workshop_registrations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'worker_id' not in columns:
            cursor.execute("ALTER TABLE workshop_registrations ADD COLUMN worker_id VARCHAR(50)")
            conn.commit()
            print("Added worker_id column to workshop_registrations")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

# ============ Initialize Database ============
with app.app_context():
    db.create_all()
    # Run migration to add missing column
    add_missing_columns()
    
    if not User.query.filter_by(role='system_admin').first():
        admin = User(
            id='sys_admin_001',
            company_id='default',
            full_name='System Administrator',
            username='systemadmin',
            role='system_admin',
            security_key='system123'
        )
        admin.set_password('System@2025')
        db.session.add(admin)
        db.session.commit()
        print("✅ System Admin created: systemadmin / System@2025")
    
    # Demo workshops
    if Workshop.query.count() == 0:
        w1 = Workshop(title="Electrical Safety Workshop", date="2025-06-15", time="10:00 AM",
                      location="Training Room A", virtual_link="https://zoom.us/123", available_seats=20)
        w2 = Workshop(title="Scaffolding Assembly", date="2025-06-20", time="2:00 PM",
                      location="Site Yard", available_seats=15)
        db.session.add_all([w1, w2])
        db.session.commit()
    
    # Demo security courses
    if SecurityCourse.query.count() == 0:
        c1 = SecurityCourse(title="Data Privacy", description="Learn how to protect company and client data.",
                            video_url="https://www.youtube.com/embed/dummy", quiz_questions='[]')
        c2 = SecurityCourse(title="Phishing Awareness", description="Recognise phishing emails and report them.",
                            video_url="https://www.youtube.com/embed/dummy2", quiz_questions='[]')
        db.session.add_all([c1, c2])
        db.session.commit()
    
    # Demo safety courses
    if SafetyCourse.query.count() == 0:
        s1 = SafetyCourse(title="Hazard Communication", role="all",
                          video_url="https://www.youtube.com/embed/dummy3", pass_score=80, expiry_days=365)
        s2 = SafetyCourse(title="Forklift Safety", role="warehouse",
                          video_url="https://www.youtube.com/embed/dummy4", pass_score=90, expiry_days=180)
        db.session.add_all([s1, s2])
        db.session.commit()
    
    # Demo projects
    if Project.query.count() == 0:
        p1 = Project(
            id='p1', company_id='default', name='Green Valley Electrical',
            location='Westlands, Nairobi', client_name='John Mwangi',
            client_phone='+254712345678', start_date='2025-01-10', agreed_cost=1250000, status='active'
        )
        p1.set_workers([{
            'name': 'Edga Morara', 'idNumber': '12345678', 'phone': '0712345678',
            'date': '2025-01-15', 'jobTitle': 'Senior Electrician',
            'workType': 'piping, mounting switch, data, TV Points, Speaker, CCTV and Socket boxes',
            'days': 30, 'wagePerDay': 1500, 'payePercent': 10, 'nssfAmount': 200,
            'nhifAmount': 150, 'advance': 0, 'workerType': 'regular'
        }])
        p2 = Project(
            id='p2', company_id='default', name='Solar Farm Phase 2',
            location='Kisumu', client_name='Rural Electrification Authority',
            client_phone='+254701234567', start_date='2025-02-15', agreed_cost=4500000, status='active'
        )
        db.session.add_all([p1, p2])
        db.session.commit()
        print("✅ Demo projects created")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 FULL ERP SYSTEM STARTING...")
    print("="*60)
    print("\n📌 LOGIN CREDENTIALS:")
    print("   Username: systemadmin")
    print("   Password: System@2025")
    print("\n🌐 Open: http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)