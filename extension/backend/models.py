# models.py
import enum
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as SQLEnum

db = SQLAlchemy()

class Status(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class Priority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# Define Models
class Company(db.Model):
    __tablename__ = 'Company' # Explicitly match Prisma model name
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    phone = db.Column(db.String, nullable=True)
    password = db.Column(db.String, nullable=False) 
    logo = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    industry = db.Column(db.String, nullable=True)
    website = db.Column(db.String, nullable=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    employees = db.relationship('Employee', back_populates='company')

class Employee(db.Model):
    __tablename__ = 'Employee'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    firstName = db.Column(db.String, nullable=False)
    lastName = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False) # Should be hashed
    position = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    refresh_token = db.Column(db.String, nullable=True) # Store Google Refresh Token
    avatar = db.Column(db.String, nullable=True) # Store Google Avatar URL
    # Store as JSON. Use db.JSON if your DB supports it natively and efficiently,
    # otherwise TEXT might be simpler if you just store the JSON string.
    browser_activity = db.Column(db.JSON, nullable=False, default=[]) # Default to empty list
    lastLogin = db.Column(db.DateTime, nullable=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    companyId = db.Column(db.String, db.ForeignKey('Company.id'), nullable=False)

    company = db.relationship('Company', back_populates='employees')
    actionPlans = db.relationship('ActionPlan', back_populates='employee', cascade="all, delete-orphan")
    documents = db.relationship('Document', back_populates='employee', cascade="all, delete-orphan")

class Document(db.Model):
    __tablename__ = 'Document'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.Text, nullable=False) # Use Text for potentially long content
    fileType = db.Column(db.String, nullable=False)
    fileSize = db.Column(db.Integer, nullable=False)
    filePath = db.Column(db.String, nullable=True)
    isArchived = db.Column(db.Boolean, default=False)
    embeddings = db.Column(db.JSON, nullable=True) # Store embeddings as JSON
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    employeeId = db.Column(db.String, db.ForeignKey('Employee.id'), nullable=False)

    employee = db.relationship('Employee', back_populates='documents')

class ActionPlan(db.Model):
    __tablename__ = 'ActionPlan'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=True) # Use Text
    urgency = db.Column(db.Integer, default=5)
    priority = db.Column(SQLEnum(Priority), default=Priority.MEDIUM)
    startDate = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Added default
    endDate = db.Column(db.DateTime, nullable=True)
    status = db.Column(SQLEnum(Status), default=Status.PENDING)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    employeeId = db.Column(db.String, db.ForeignKey('Employee.id'), nullable=False)

    employee = db.relationship('Employee', back_populates='actionPlans')
    actions = db.relationship('Action', back_populates='actionPlan', cascade="all, delete-orphan")

class Action(db.Model):
    __tablename__ = 'Action'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=True) # Use Text
    dueDate = db.Column(db.DateTime, nullable=True)
    code = db.Column(db.String, nullable=True) # e.g., reference to code snippet/commit
    status = db.Column(SQLEnum(Status), default=Status.PENDING)
    priority = db.Column(SQLEnum(Priority), default=Priority.MEDIUM)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    actionPlanId = db.Column(db.String, db.ForeignKey('ActionPlan.id'), nullable=False)

    actionPlan = db.relationship('ActionPlan', back_populates='actions')