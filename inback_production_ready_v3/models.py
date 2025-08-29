from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Import db from app after it's initialized
try:
    from app import db
except ImportError:
    # Fallback for when app is not yet available
    class Base(DeclarativeBase):
        pass
    db = SQLAlchemy(model_class=Base)


class City(db.Model):
    """City model for multi-city support"""
    __tablename__ = 'cities'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    
    # Map configuration
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    zoom_level = db.Column(db.Integer, default=12)
    
    # SEO and content
    description = db.Column(db.Text, nullable=True)
    meta_title = db.Column(db.String(200), nullable=True)
    meta_description = db.Column(db.String(300), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<City {self.name}>'


class Developer(db.Model):
    """Developer/Builder model with full company information"""
    __tablename__ = 'developers'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    
    # Company Information
    full_name = db.Column(db.String(300), nullable=True)  # ООО "Компания"
    established_year = db.Column(db.Integer, nullable=True)  # Год основания
    description = db.Column(db.Text, nullable=True)  # Описание компании
    logo_url = db.Column(db.String(300), nullable=True)
    
    # Contact Information
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    website = db.Column(db.String(200), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    
    # Location and Map
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    zoom_level = db.Column(db.Integer, default=13)
    
    # Statistics
    total_complexes = db.Column(db.Integer, default=0)
    total_properties = db.Column(db.Integer, default=0)
    properties_sold = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=4.8)
    experience_years = db.Column(db.Integer, default=10)
    
    # Financial Information
    min_price = db.Column(db.Integer, nullable=True)
    max_cashback_percent = db.Column(db.Float, default=10.0)
    
    # Company Details
    inn = db.Column(db.String(20), nullable=True)  # ИНН
    kpp = db.Column(db.String(20), nullable=True)  # КПП
    ogrn = db.Column(db.String(20), nullable=True)  # ОГРН
    legal_address = db.Column(db.String(300), nullable=True)
    bank_name = db.Column(db.String(200), nullable=True)
    bank_bik = db.Column(db.String(20), nullable=True)
    bank_account = db.Column(db.String(30), nullable=True)
    
    # Features
    features = db.Column(db.Text, nullable=True)  # JSON array of features
    infrastructure = db.Column(db.Text, nullable=True)  # JSON array of infrastructure
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_partner = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Developer {self.name}>'


class DeveloperAppointment(db.Model):
    """Developer appointment model"""
    __tablename__ = 'developer_appointments'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Allow null for anonymous applications
    property_id = db.Column(db.String(50), nullable=True)  # Property ID from JSON - allow null for general applications
    developer_id = db.Column(db.Integer, db.ForeignKey('developers.id'), nullable=True)
    developer_name = db.Column(db.String(200), nullable=False)
    complex_name = db.Column(db.String(200), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(50), default='Запланирована')  # Запланирована, Завершена, Отменена
    client_name = db.Column(db.String(200), nullable=False)
    client_phone = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='developer_appointments')
    developer = db.relationship('Developer', backref='appointments')


class CallbackRequest(db.Model):
    """Callback request model"""
    __tablename__ = 'callback_requests'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    preferred_time = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Quiz responses
    interest = db.Column(db.String(100), nullable=True)  # What they're interested in
    budget = db.Column(db.String(50), nullable=True)    # Budget range
    timing = db.Column(db.String(50), nullable=True)    # When they plan to buy
    
    # Status tracking
    status = db.Column(db.String(50), default='Новая')  # Новая, Обработана, Звонок совершен
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=True)
    manager_notes = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    assigned_manager = db.relationship('Manager', backref='callback_requests')
    
    def __repr__(self):
        return f'<CallbackRequest {self.name} - {self.phone}>'

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    telegram_id = db.Column(db.String(50), nullable=True)  # Telegram chat ID
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Allow null for users created by managers
    temp_password_hash = db.Column(db.String(256), nullable=True)  # Temporary password for new users
    created_by_admin = db.Column(db.Boolean, default=False)  # Track if user created by admin
    
    # Notification preferences
    preferred_contact = db.Column(db.String(20), default='email')  # phone, email, telegram, whatsapp, both
    email_notifications = db.Column(db.Boolean, default=True)
    telegram_notifications = db.Column(db.Boolean, default=False)
    notify_recommendations = db.Column(db.Boolean, default=True)
    notify_saved_searches = db.Column(db.Boolean, default=True)
    notify_applications = db.Column(db.Boolean, default=True)
    notify_cashback = db.Column(db.Boolean, default=True)
    notify_marketing = db.Column(db.Boolean, default=False)
    
    # Profile info
    profile_image = db.Column(db.String(200), default='https://randomuser.me/api/portraits/men/32.jpg')
    user_id = db.Column(db.String(20), unique=True, nullable=False)  # CB12345678 format
    role = db.Column(db.String(20), default='buyer')  # buyer, manager, admin
    
    # Status and verification
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    is_demo = db.Column(db.Boolean, default=False)  # Demo account flag
    verified = db.Column(db.Boolean, default=False)  # Account verification status
    
    # Client management
    registration_source = db.Column(db.String(50), default='Website')
    client_notes = db.Column(db.Text, nullable=True)
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=True)
    client_status = db.Column(db.String(50), default='Новый')
    
    # Registration quiz preferences
    preferred_district = db.Column(db.String(100))  # Step 1: District selection
    property_type = db.Column(db.String(50))  # Step 2: Property type (квартира, таунхаус, дом)
    room_count = db.Column(db.String(20))  # Step 3: Room count  
    budget_range = db.Column(db.String(50))  # Step 4: Budget range
    quiz_completed = db.Column(db.Boolean, default=False)
    
    # Relationship to manager
    assigned_manager = db.relationship('Manager', backref='assigned_clients')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    cashback_records = db.relationship('CashbackRecord', backref='user', lazy=True)
    applications = db.relationship('Application', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)
    saved_searches = db.relationship('SavedSearch', back_populates='user', lazy=True)
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.user_id:
            self.user_id = self.generate_user_id()
    
    def generate_user_id(self):
        """Generate unique user ID in format CB12345678"""
        import random
        while True:
            user_id = f"CB{random.randint(10000000, 99999999)}"
            if not User.query.filter_by(user_id=user_id).first():
                return user_id
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        if not self.password_hash:
            return False  # No password set yet
        return check_password_hash(self.password_hash, password)
    
    def needs_password_setup(self):
        """Check if user needs to set up password"""
        return not self.password_hash
    
    def generate_verification_token(self):
        """Generate verification token"""
        self.verification_token = secrets.token_urlsafe(32)
        return self.verification_token
    
    def get_total_cashback(self):
        """Get total cashback amount"""
        total = sum(record.amount for record in self.cashback_records if record.status == 'paid')
        return total or 0
    
    def get_pending_cashback(self):
        """Get pending cashback amount"""
        total = sum(record.amount for record in self.cashback_records if record.status == 'pending')
        return total or 0
    
    def __repr__(self):
        return f'<User {self.email}>'

class Manager(UserMixin, db.Model):
    """Manager model for staff authentication and client management"""
    __tablename__ = 'managers'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    position = db.Column(db.String(50), default='Менеджер')
    
    # Manager permissions and limits
    can_approve_cashback = db.Column(db.Boolean, default=True)
    can_manage_documents = db.Column(db.Boolean, default=True)
    can_create_collections = db.Column(db.Boolean, default=True)
    max_cashback_approval = db.Column(db.Integer, default=500000)  # Maximum amount they can approve
    
    # Status and profile
    is_active = db.Column(db.Boolean, default=True)
    profile_image = db.Column(db.String(200), default='https://randomuser.me/api/portraits/men/45.jpg')
    manager_id = db.Column(db.String(20), unique=True, nullable=False)  # MNG12345678 format
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        super(Manager, self).__init__(**kwargs)
        if not self.manager_id:
            self.manager_id = self.generate_manager_id()
    
    def generate_manager_id(self):
        """Generate unique manager ID in format MNG12345678"""
        import random
        while True:
            manager_id = f"MNG{random.randint(10000000, 99999999)}"
            if not Manager.query.filter_by(manager_id=manager_id).first():
                return manager_id
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def name(self):
        """Alias for full_name for compatibility"""
        return self.full_name
    
    def get_client_count(self):
        """Get number of assigned clients"""
        return User.query.filter_by(assigned_manager_id=self.id).count()
    
    def get_active_applications(self):
        """Get active cashback applications from assigned clients"""
        return CashbackApplication.query.join(User).filter(
            User.assigned_manager_id == self.id,
            CashbackApplication.status.in_(['На рассмотрении', 'Требуются документы'])
        ).count()
    
    def get_total_approved_cashback(self):
        """Get total cashback amount approved by this manager"""
        applications = CashbackApplication.query.join(User).filter(
            User.assigned_manager_id == self.id,
            CashbackApplication.status == 'Одобрена'
        ).all()
        return sum(app.cashback_amount for app in applications)
    
    def get_active_deals_count(self):
        """Get count of active deals for this manager"""
        return CashbackApplication.query.join(User).filter(
            User.assigned_manager_id == self.id,
            CashbackApplication.status.in_(['На рассмотрении', 'Требуются документы', 'Одобрена'])
        ).count()
    
    def to_dict(self):
        """Convert manager to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'position': self.position,
            'manager_id': self.manager_id,
            'is_active': self.is_active,
            'profile_image': self.profile_image,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    def __repr__(self):
        return f'<Manager {self.email}>'


class Collection(db.Model):
    __tablename__ = 'collections'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_by_manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(50), default='Черновик')  # Черновик, Отправлена, Просмотрена
    is_public = db.Column(db.Boolean, default=False)
    tags = db.Column(db.Text)  # JSON format: ["семейная", "премиум", "инвестиция"]
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    viewed_at = db.Column(db.DateTime)
    
    # Relationships
    created_by = db.relationship('Manager', backref='created_collections')
    assigned_to = db.relationship('User', backref='received_collections')
    properties = db.relationship('CollectionProperty', backref='collection', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Collection {self.title}>'


class CollectionProperty(db.Model):
    __tablename__ = 'collection_properties'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('collections.id'), nullable=False)
    property_id = db.Column(db.String(100), nullable=False)  # ID from properties.json
    property_name = db.Column(db.String(255))
    property_price = db.Column(db.Integer)
    complex_name = db.Column(db.String(255))
    property_type = db.Column(db.String(100))
    property_size = db.Column(db.Float)
    manager_note = db.Column(db.Text)  # Комментарий менеджера к конкретной квартире
    order_index = db.Column(db.Integer, default=0)  # Порядок в подборке
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CollectionProperty {self.property_name}>'


class Admin(db.Model):
    """Administrator model with full system access"""
    __tablename__ = 'admins'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    
    # Admin specific fields
    admin_id = db.Column(db.String(20), unique=True, nullable=False)  # ADM12345678 format
    role = db.Column(db.String(50), default='Super Admin')  # Super Admin, Content Admin, Finance Admin
    permissions = db.Column(db.Text)  # JSON format permissions
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_super_admin = db.Column(db.Boolean, default=False)
    
    # Profile
    profile_image = db.Column(db.String(200), default='https://randomuser.me/api/portraits/men/1.jpg')
    phone = db.Column(db.String(20), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        super(Admin, self).__init__(**kwargs)
        if not self.admin_id:
            self.admin_id = self.generate_admin_id()
        if not self.permissions:
            self.permissions = '{"all": true}'  # Default full permissions
    
    def generate_admin_id(self):
        """Generate unique admin ID in format ADM12345678"""
        import random
        while True:
            admin_id = f"ADM{random.randint(10000000, 99999999)}"
            if not Admin.query.filter_by(admin_id=admin_id).first():
                return admin_id
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Check if admin has specific permission"""
        import json
        try:
            perms = json.loads(self.permissions)
            return perms.get('all', False) or perms.get(permission, False)
        except:
            return False
    
    def get_total_users(self):
        """Get total number of users"""
        return User.query.count()
    
    def get_total_managers(self):
        """Get total number of managers"""
        return Manager.query.count()
    
    def get_total_cashback_paid(self):
        """Get total cashback amount paid"""
        applications = CashbackApplication.query.filter_by(status='Выплачена').all()
        return sum(app.cashback_amount for app in applications)
    
    def get_total_cashback_approved(self):
        """Get total cashback amount approved"""
        applications = CashbackApplication.query.filter_by(status='Одобрена').all()
        return sum(app.cashback_amount for app in applications)
    
    def __repr__(self):
        return f'<Admin {self.email}>'


class BlogPost(db.Model):
    """Blog post model for content management"""
    __tablename__ = 'blog_posts'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text, nullable=True)
    
    # SEO fields
    meta_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.Text, nullable=True)
    meta_keywords = db.Column(db.String(500), nullable=True)
    
    # Content management
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    featured_image = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.Text, nullable=True)  # JSON array of tags
    
    # Author info
    author_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    author = db.relationship('Admin', backref='blog_posts')
    
    # Publishing
    published_at = db.Column(db.DateTime, nullable=True)
    scheduled_for = db.Column(db.DateTime, nullable=True)
    
    # Analytics
    views_count = db.Column(db.Integer, default=0)
    likes_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super(BlogPost, self).__init__(**kwargs)
        if not self.slug and self.title:
            self.slug = self.generate_slug(self.title)
    
    def generate_slug(self, title):
        """Generate URL-friendly slug from title"""
        import re
        # Transliterate Cyrillic to Latin
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        slug = title.lower()
        for ru, en in translit_map.items():
            slug = slug.replace(ru, en)
        
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure uniqueness
        original_slug = slug
        counter = 1
        while BlogPost.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
    
    def publish(self):
        """Publish the blog post"""
        self.status = 'published'
        self.published_at = datetime.utcnow()
        db.session.commit()
    
    def unpublish(self):
        """Unpublish the blog post"""
        self.status = 'draft'
        self.published_at = None
        db.session.commit()
    
    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<BlogPost {self.title}>'

class CashbackApplication(db.Model):
    __tablename__ = 'cashback_applications'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    property_id = db.Column(db.String(50), nullable=True)  # Property ID from JSON data
    property_name = db.Column(db.String(200), nullable=False)
    property_type = db.Column(db.String(50), nullable=False)  # 1-комн, 2-комн, студия
    property_size = db.Column(db.Float, nullable=False)  # площадь в м²
    property_price = db.Column(db.Integer, nullable=False)  # цена в рублях
    complex_name = db.Column(db.String(200), nullable=False)
    developer_name = db.Column(db.String(200), nullable=False)
    cashback_amount = db.Column(db.Integer, nullable=False)  # сумма кешбека в рублях
    cashback_percent = db.Column(db.Float, nullable=False)  # процент кешбека
    status = db.Column(db.String(50), default='На рассмотрении')  # На рассмотрении, Одобрена, Отклонена, Выплачена
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    approved_date = db.Column(db.DateTime)
    payout_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Manager fields
    approved_by_manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=True)
    manager_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='cashback_applications')
    approved_by_manager = db.relationship('Manager', foreign_keys=[approved_by_manager_id])

class FavoriteProperty(db.Model):
    __tablename__ = 'favorite_properties'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    property_id = db.Column(db.String(50), nullable=True)  # Property ID from JSON data
    property_name = db.Column(db.String(200), nullable=False)
    property_type = db.Column(db.String(50), nullable=True)
    property_size = db.Column(db.Float, nullable=True)
    property_price = db.Column(db.Integer, nullable=True)
    complex_name = db.Column(db.String(200), nullable=True)
    developer_name = db.Column(db.String(200), nullable=True)
    property_image = db.Column(db.String(500))
    property_url = db.Column(db.String(500))
    cashback_amount = db.Column(db.Integer)
    cashback_percent = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='favorite_properties')


class FavoriteComplex(db.Model):
    __tablename__ = 'favorite_complexes'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    complex_id = db.Column(db.String(50), nullable=True)  # Complex ID from JSON data
    complex_name = db.Column(db.String(200), nullable=False)
    developer_name = db.Column(db.String(200), nullable=True)
    complex_address = db.Column(db.String(500), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    min_price = db.Column(db.Integer, nullable=True)
    max_price = db.Column(db.Integer, nullable=True)
    complex_image = db.Column(db.String(500))
    complex_url = db.Column(db.String(500))
    status = db.Column(db.String(50), nullable=True)  # В продаже, Построен, Строится
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='favorite_complexes')

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'complex_id': self.complex_id,
            'complex_name': self.complex_name,
            'developer_name': self.developer_name,
            'complex_address': self.complex_address,
            'district': self.district,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'complex_image': self.complex_image,
            'complex_url': self.complex_url,
            'status': self.status,
            'created_at': self.created_at.strftime('%d.%m.%Y в %H:%M') if self.created_at else None
        }

class Document(db.Model):
    __tablename__ = 'documents'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # pdf, doc, docx, jpg, png
    file_size = db.Column(db.Integer, nullable=False)  # размер в байтах
    file_path = db.Column(db.String(500), nullable=False)
    document_type = db.Column(db.String(100))  # паспорт, справка о доходах, и т.д.
    status = db.Column(db.String(50), default='На проверке')  # На проверке, Проверен, Отклонен
    reviewed_at = db.Column(db.DateTime)
    reviewer_notes = db.Column(db.Text)
    reviewed_by_manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='documents')
    reviewed_by_manager = db.relationship('Manager', foreign_keys=[reviewed_by_manager_id])


class SavedSearch(db.Model):
    """User's saved search parameters"""
    __tablename__ = 'saved_searches'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # User-defined name for the search
    description = db.Column(db.Text)  # Optional description
    
    # Search parameters
    search_type = db.Column(db.String(20), default='properties')  # 'properties' or 'complexes'
    location = db.Column(db.String(200))  # District, street, etc.
    property_type = db.Column(db.String(50))  # 1-комн, 2-комн, etc.
    price_min = db.Column(db.Integer)
    price_max = db.Column(db.Integer)
    size_min = db.Column(db.Float)
    size_max = db.Column(db.Float)
    developer = db.Column(db.String(200))
    complex_name = db.Column(db.String(200))
    floor_min = db.Column(db.Integer)
    floor_max = db.Column(db.Integer)
    cashback_min = db.Column(db.Integer)
    
    # Additional filters (JSON format for flexibility)
    additional_filters = db.Column(db.Text)  # JSON string with any other filters
    
    # Search settings
    notify_new_matches = db.Column(db.Boolean, default=True)  # Notify when new properties match
    last_notification_sent = db.Column(db.DateTime)
    created_from_quiz = db.Column(db.Boolean, default=False)  # Created from registration quiz
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='saved_searches')
    
    def to_dict(self):
        """Convert search to dictionary for easy JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'search_type': self.search_type,
            'location': self.location,
            'property_type': self.property_type,
            'price_min': self.price_min,
            'price_max': self.price_max,
            'size_min': self.size_min,
            'size_max': self.size_max,
            'developer': self.developer,
            'complex_name': self.complex_name,
            'floor_min': self.floor_min,
            'floor_max': self.floor_max,
            'cashback_min': self.cashback_min,
            'additional_filters': self.additional_filters,
            'notify_new_matches': self.notify_new_matches,
            'created_at': self.created_at.strftime('%d.%m.%Y в %H:%M') if self.created_at else None,
            'last_used': self.last_used.strftime('%d.%m.%Y в %H:%M') if self.last_used else None
        }
    
    def __repr__(self):
        return f'<SavedSearch {self.name}>'

class ManagerSavedSearch(db.Model):
    """Manager's saved search parameters for sending to clients"""
    __tablename__ = 'manager_saved_searches'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Manager-defined name for the search
    description = db.Column(db.Text)  # Optional description
    
    # Search parameters (same structure as SavedSearch for compatibility)
    search_type = db.Column(db.String(20), default='properties')  # 'properties' or 'complexes'
    location = db.Column(db.String(200))  # District, street, etc.
    property_type = db.Column(db.String(50))  # 1-комн, 2-комн, etc.
    price_min = db.Column(db.Integer)
    price_max = db.Column(db.Integer)
    size_min = db.Column(db.Float)
    size_max = db.Column(db.Float)
    developer = db.Column(db.String(200))
    complex_name = db.Column(db.String(200))
    floor_min = db.Column(db.Integer)
    floor_max = db.Column(db.Integer)
    cashback_min = db.Column(db.Integer)
    
    # Additional filters (JSON format for flexibility) 
    additional_filters = db.Column(db.Text)  # JSON string with any other filters
    
    # Manager-specific fields
    is_template = db.Column(db.Boolean, default=False)  # Whether this can be used as template
    usage_count = db.Column(db.Integer, default=0)  # How many times sent to clients
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    manager = db.relationship('Manager', backref='saved_searches')
    
    def to_dict(self):
        """Convert search to dictionary for easy JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'search_type': self.search_type,
            'location': self.location,
            'property_type': self.property_type,
            'price_min': self.price_min,
            'price_max': self.price_max,
            'size_min': self.size_min,
            'size_max': self.size_max,
            'developer': self.developer,
            'complex_name': self.complex_name,
            'floor_min': self.floor_min,
            'floor_max': self.floor_max,
            'cashback_min': self.cashback_min,
            'additional_filters': self.additional_filters,
            'is_template': self.is_template,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }
    
    def __repr__(self):
        return f'<ManagerSavedSearch {self.name}>'

class SentSearch(db.Model):
    """Record of searches sent from managers to clients"""
    __tablename__ = 'sent_searches'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manager_search_id = db.Column(db.Integer, db.ForeignKey('manager_saved_searches.id'), nullable=True)
    
    # Copy of search parameters at time of sending (for history)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    additional_filters = db.Column(db.Text)  # JSON string with filters
    
    # Status tracking
    status = db.Column(db.String(20), default='sent')  # sent, viewed, applied, expired
    viewed_at = db.Column(db.DateTime)
    applied_at = db.Column(db.DateTime) 
    expires_at = db.Column(db.DateTime)  # Optional expiration
    
    # Timestamps
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    manager = db.relationship('Manager', backref='sent_searches')
    client = db.relationship('User', backref='received_searches')
    manager_search = db.relationship('ManagerSavedSearch', backref='sent_instances')
    
    def __repr__(self):
        return f'<SentSearch {self.name} from Manager {self.manager_id} to User {self.client_id}>'

class UserNotification(db.Model):
    __tablename__ = 'user_notifications'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info')  # info, success, warning, error
    icon = db.Column(db.String(50), default='fas fa-info-circle')
    is_read = db.Column(db.Boolean, default=False)
    action_url = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='user_notifications')


class CashbackRecord(db.Model):
    """Cashback record model"""
    __tablename__ = 'cashback_records'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Property details
    property_id = db.Column(db.Integer, nullable=True)  # Reference to property
    property_name = db.Column(db.String(200), nullable=False)
    property_price = db.Column(db.Float, nullable=False)
    
    # Cashback details
    amount = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float, nullable=False)  # 2.5, 3.0, etc.
    status = db.Column(db.String(20), default='pending')  # pending, approved, paid, rejected
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<CashbackRecord {self.property_name}: {self.amount}₽>'


class Application(db.Model):
    """User application model"""
    __tablename__ = 'applications'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Allow null for anonymous applications
    
    # Contact information for anonymous applications
    contact_name = db.Column(db.String(200), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    
    # Application details
    property_id = db.Column(db.String(50), nullable=True)  # Changed to match other models
    property_name = db.Column(db.String(200), nullable=False)
    complex_name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='new')  # new, in_progress, approved, rejected, completed
    
    # Contact info
    message = db.Column(db.Text, nullable=True)
    preferred_contact = db.Column(db.String(20), default='email')  # phone, email, telegram, both
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Application {self.property_name}>'


class Favorite(db.Model):
    """User favorites model"""
    __tablename__ = 'favorites'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    property_id = db.Column(db.Integer, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'property_id', name='unique_user_property'),)
    
    def __repr__(self):
        return f'<Favorite user:{self.user_id} property:{self.property_id}>'


class Notification(db.Model):
    """User notifications model"""
    __tablename__ = 'notifications'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Notification details
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, error
    icon = db.Column(db.String(50), default='fas fa-info-circle')
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='notifications', lazy=True)
    
    def __repr__(self):
        return f'<Notification {self.title}>'

class ClientPropertyRecommendation(db.Model):
    """Model for manager-to-client property recommendations"""
    __tablename__ = 'client_property_recommendations'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Manager who sent
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)   # Client who receives
    search_id = db.Column(db.Integer, db.ForeignKey('saved_searches.id'), nullable=False)  # Search being shared
    message = db.Column(db.Text)  # Personal message from manager
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    viewed_at = db.Column(db.DateTime)
    
    # Relationships
    manager = db.relationship('User', foreign_keys=[manager_id], backref='sent_property_recommendations')
    client = db.relationship('User', foreign_keys=[client_id], backref='received_property_recommendations')
    search = db.relationship('SavedSearch', backref='property_recommendations')
    
    def to_dict(self):
        return {
            'id': self.id,
            'manager': {
                'id': self.manager.id,
                'full_name': self.manager.full_name,
                'email': self.manager.email
            },
            'client': {
                'id': self.client.id,
                'full_name': self.client.full_name,
                'email': self.client.email
            },
            'search': self.search.to_dict(),
            'message': self.message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None
        }


class SearchCategory(db.Model):
    """Search categories for autocomplete"""
    __tablename__ = 'search_categories'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(50), nullable=False)  # district, developer, complex, rooms, street
    slug = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class District(db.Model):
    """Districts in Krasnodar"""
    __tablename__ = 'districts'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)


class ResidentialComplex(db.Model):
    """Residential complexes"""
    __tablename__ = 'residential_complexes'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'))
    developer_id = db.Column(db.Integer, db.ForeignKey('developers.id'))
    cashback_rate = db.Column(db.Float, default=5.0, nullable=False)
    district = db.relationship('District', backref='complexes')
    developer = db.relationship('Developer', backref='complexes')


class Street(db.Model):
    """Streets in Krasnodar"""
    __tablename__ = 'streets'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'))
    district = db.relationship('District', backref='streets')


class RoomType(db.Model):
    """Room types for apartments"""
    __tablename__ = 'room_types'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # "1-комнатная", "2-комнатная", "студия"
    rooms_count = db.Column(db.Integer)

class CashbackPayout(db.Model):
    """Model for cashback payout requests"""
    __tablename__ = 'cashback_payouts'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    status = db.Column(db.String(50), default='Запрошена')  # Запрошена, Одобрена, Выплачена, Отклонена
    payment_method = db.Column(db.String(100), nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='cashback_payouts')
    
    def __repr__(self):
        return f'<CashbackPayout {self.id}: {self.amount} ₽>'

class RecommendationCategory(db.Model):
    """Categories for organizing recommendations by client and manager"""
    __tablename__ = 'recommendation_categories'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # e.g., "Однокомнатные до 5 млн, Черемушки"
    description = db.Column(db.Text)  # Optional description
    
    # Ownership
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Category settings
    color = db.Column(db.String(20), default='blue')  # Color theme for UI
    is_active = db.Column(db.Boolean, default=True)
    filters = db.Column(db.Text, nullable=True)  # JSON string of filter criteria
    
    # Statistics
    recommendations_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    manager = db.relationship('Manager', backref='recommendation_categories')
    client = db.relationship('User', backref='recommendation_categories')
    recommendations = db.relationship('Recommendation', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<RecommendationCategory {self.name} for {self.client.full_name}>'

class Recommendation(db.Model):
    """Manager recommendations to clients - properties or complexes"""
    __tablename__ = 'recommendations'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('recommendation_categories.id'), nullable=True)
    
    # Recommendation details
    title = db.Column(db.String(255), nullable=False)  # Custom title from manager
    description = db.Column(db.Text)  # Manager's personal note/recommendation
    recommendation_type = db.Column(db.String(20), nullable=False)  # 'property' or 'complex'
    
    # Item details (property or complex)
    item_id = db.Column(db.String(100), nullable=False)  # Property ID or complex ID from JSON
    item_name = db.Column(db.String(255), nullable=False)  # Property/complex name
    item_data = db.Column(db.Text)  # JSON with full item details for history
    
    # Manager notes and highlights
    manager_notes = db.Column(db.Text)  # Why recommended
    highlighted_features = db.Column(db.Text)  # JSON array of key features to highlight
    priority_level = db.Column(db.String(20), default='normal')  # urgent, high, normal, low
    
    # Status tracking
    status = db.Column(db.String(20), default='sent')  # sent, viewed, interested, not_interested, scheduled_viewing
    viewed_at = db.Column(db.DateTime)
    responded_at = db.Column(db.DateTime)  # When client responded
    client_response = db.Column(db.String(20))  # interested, not_interested, need_more_info
    client_notes = db.Column(db.Text)  # Client's feedback
    
    # Scheduling
    viewing_requested = db.Column(db.Boolean, default=False)
    viewing_scheduled_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # Optional expiration for offer
    
    # Relationships
    manager = db.relationship('Manager', backref='sent_recommendations')
    client = db.relationship('User', backref='received_recommendations')
    
    def to_dict(self):
        """Convert recommendation to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'recommendation_type': self.recommendation_type,
            'item_id': self.item_id,
            'item_name': self.item_name,
            'manager_notes': self.manager_notes,
            'priority_level': self.priority_level,
            'status': self.status,
            'client_response': self.client_response,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'highlighted_features': self.highlighted_features,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'client_notes': self.client_notes,
            'viewing_requested': self.viewing_requested,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None,
            'viewing_scheduled_at': self.viewing_scheduled_at.isoformat() if self.viewing_scheduled_at else None
        }
    
    def __repr__(self):
        return f'<Recommendation {self.title} from Manager {self.manager_id} to User {self.client_id}>'

class RecommendationTemplate(db.Model):
    """Templates for common recommendations that managers can reuse"""
    __tablename__ = 'recommendation_templates'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    
    # Template details
    name = db.Column(db.String(255), nullable=False)  # Template name
    description = db.Column(db.Text)  # Template description
    recommendation_type = db.Column(db.String(20), nullable=False)  # 'property' or 'complex'
    
    # Default content
    default_title = db.Column(db.String(255))
    default_description = db.Column(db.Text)
    default_notes = db.Column(db.Text)
    default_highlighted_features = db.Column(db.Text)  # JSON array
    default_priority = db.Column(db.String(20), default='normal')
    
    # Template settings
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # Relationships
    manager = db.relationship('Manager', backref='recommendation_templates')
    
    def __repr__(self):
        return f'<RecommendationTemplate {self.name}>'


class BlogCategory(db.Model):
    """Blog categories for organizing articles"""
    __tablename__ = 'blog_categories'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='blue')
    icon = db.Column(db.String(50))  # FontAwesome icon class
    
    # SEO
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.String(300))
    
    # Ordering and visibility
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Statistics
    articles_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    articles = db.relationship('BlogArticle', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<BlogCategory {self.name}>'


class BlogArticle(db.Model):
    """Blog articles with full content management"""
    __tablename__ = 'blog_articles'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    excerpt = db.Column(db.String(500))  # Short description
    content = db.Column(db.Text, nullable=False)  # Full HTML content
    
    # Author info
    author_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=False)
    author_name = db.Column(db.String(100))  # Override author display name
    
    # Category
    category_id = db.Column(db.Integer, db.ForeignKey('blog_categories.id'), nullable=False)
    
    # Publishing
    status = db.Column(db.String(20), default='draft')  # draft, published, scheduled, archived
    published_at = db.Column(db.DateTime)
    scheduled_at = db.Column(db.DateTime)  # For scheduled publishing
    
    # SEO and meta
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.String(300))
    meta_keywords = db.Column(db.String(500))
    featured_image = db.Column(db.String(300))  # URL to featured image
    featured_image_alt = db.Column(db.String(200))
    
    # Content settings
    is_featured = db.Column(db.Boolean, default=False)
    allow_comments = db.Column(db.Boolean, default=True)
    
    # Statistics
    views_count = db.Column(db.Integer, default=0)
    reading_time = db.Column(db.Integer, default=0)  # Estimated reading time in minutes
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('Manager', backref='blog_articles')
    comments = db.relationship('BlogComment', backref='article', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('BlogTag', secondary='blog_article_tags', backref='articles')
    
    def __repr__(self):
        return f'<BlogArticle {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'excerpt': self.excerpt,
            'content': self.content,
            'status': self.status,
            'category': {
                'id': self.category.id,
                'name': self.category.name,
                'slug': self.category.slug
            },
            'author': {
                'id': self.author.id,
                'name': self.author_name or self.author.full_name
            },
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'views_count': self.views_count,
            'reading_time': self.reading_time,
            'featured_image': self.featured_image,
            'is_featured': self.is_featured
        }


class BlogTag(db.Model):
    """Tags for blog articles"""
    __tablename__ = 'blog_tags'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    slug = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    # Statistics
    usage_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BlogTag {self.name}>'


# Association table for many-to-many relationship between articles and tags
blog_article_tags = db.Table('blog_article_tags',
    db.Column('article_id', db.Integer, db.ForeignKey('blog_articles.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('blog_tags.id'), primary_key=True)
)


class BlogComment(db.Model):
    """Comments on blog articles"""
    __tablename__ = 'blog_comments'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('blog_articles.id'), nullable=False)
    
    # Author info
    author_name = db.Column(db.String(100), nullable=False)
    author_email = db.Column(db.String(120), nullable=False)
    author_website = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # If registered user
    
    # Comment content
    content = db.Column(db.Text, nullable=False)
    
    # Moderation
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, spam
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(300))
    
    # Threading support
    parent_id = db.Column(db.Integer, db.ForeignKey('blog_comments.id'))
    parent = db.relationship('BlogComment', remote_side=[id], backref='replies')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='blog_comments')
    
    def __repr__(self):
        return f'<BlogComment by {self.author_name}>'

class Property(db.Model):
    """Property/Apartment model for real estate listings"""
    __tablename__ = 'properties'
    __table_args__ = {"extend_existing": True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic property information
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    
    # Property details
    rooms = db.Column(db.Integer, nullable=True)  # Количество комнат (0 для студии)
    area = db.Column(db.Float, nullable=True)  # Площадь в м²
    floor = db.Column(db.Integer, nullable=True)  # Этаж
    total_floors = db.Column(db.Integer, nullable=True)  # Всего этажей в доме
    
    # Pricing
    price = db.Column(db.Integer, nullable=True)  # Цена в рублях
    price_per_sqm = db.Column(db.Integer, nullable=True)  # Цена за м²
    
    # Location and relations
    developer_id = db.Column(db.Integer, db.ForeignKey('developers.id'), nullable=True)
    complex_id = db.Column(db.Integer, db.ForeignKey('residential_complexes.id'), nullable=True)
    district_id = db.Column(db.Integer, db.ForeignKey('districts.id'), nullable=True)
    
    # Status and availability
    status = db.Column(db.String(50), default='available')  # available, sold, reserved
    is_active = db.Column(db.Boolean, default=True)
    
    # Images and media
    main_image = db.Column(db.String(300), nullable=True)
    gallery_images = db.Column(db.Text, nullable=True)  # JSON array of image URLs
    
    # Technical details
    building_type = db.Column(db.String(100), nullable=True)  # монолит, кирпич, панель
    ceiling_height = db.Column(db.Float, nullable=True)  # Высота потолков
    
    # Coordinates for maps
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    
    # Metadata
    source_url = db.Column(db.String(300), nullable=True)  # URL источника данных
    scraped_at = db.Column(db.DateTime, nullable=True)  # Дата парсинга
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    developer = db.relationship('Developer', backref='properties')
    complex = db.relationship('ResidentialComplex', backref='properties')
    district = db.relationship('District', backref='properties')
    
    def __repr__(self):
        return f'<Property {self.title}>'
    
    @property
    def formatted_price(self):
        if self.price:
            if self.price >= 1000000:
                return f"{self.price / 1000000:.1f} млн ₽"
            elif self.price >= 1000:
                return f"{self.price / 1000:.0f} тыс ₽"
            return f"{self.price} ₽"
        return "Цена не указана"
    
    @property
    def room_description(self):
        if self.rooms == 0:
            return "Студия"
        elif self.rooms == 1:
            return "1-комнатная"
        elif self.rooms in [2, 3, 4]:
            return f"{self.rooms}-комнатная"
        elif self.rooms:
            return f"{self.rooms}-комн."
        return "Тип не указан"
