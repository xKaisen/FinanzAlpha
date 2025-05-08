from sqlalchemy import (
    Column, Integer, String, DateTime, JSON, Boolean, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id            = Column(Integer, primary_key=True)
    username      = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin      = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SomeModel(Base):
    __tablename__ = 'some_model'
    id            = Column(Integer, primary_key=True)
    name          = Column(String, nullable=False)
    last_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RecurringEntry(Base):
    __tablename__ = 'recurring_entries'
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey('users.id'), nullable=False)
    description   = Column(String, nullable=False)
    usage         = Column(String, nullable=False)
    amount        = Column(Integer, nullable=False)
    duration      = Column(Integer, nullable=False)  # in Monaten
    start_date    = Column(DateTime, default=datetime.utcnow)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transaction(Base):
    __tablename__ = 'transactions'
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey('users.id'), nullable=False)
    date         = Column(DateTime, nullable=False, default=datetime.utcnow)
    description  = Column(String, nullable=False)
    usage        = Column(String, nullable=False)
    amount       = Column(Integer, nullable=False)
    paid         = Column(Boolean, nullable=False, default=False)
    recurring_id = Column(Integer, ForeignKey('recurring_entries.id'), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LocalChange(Base):
    __tablename__ = 'changelog_local'
    id          = Column(Integer, primary_key=True)
    table_name  = Column(String,  nullable=False)
    operation   = Column(String,  nullable=False)
    row_id      = Column(Integer, nullable=False)
    data        = Column(JSON,    nullable=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)

class LocalChangeRemote(Base):
    __tablename__ = 'changelog_remote'
    id          = Column(Integer, primary_key=True)
    table_name  = Column(String,  nullable=False)
    operation   = Column(String,  nullable=False)
    row_id      = Column(Integer, nullable=False)
    data        = Column(JSON,    nullable=True)
    timestamp   = Column(DateTime, default=datetime.utcnow)
