from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Date, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

# Declarative Base für alle ORM-Modelle
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    transactions = relationship(
        'Transaction', back_populates='user', cascade='all, delete-orphan'
    )
    recurring_entries = relationship(
        'RecurringEntry', back_populates='user', cascade='all, delete-orphan'
    )
    fix_suggestions = relationship(
        'FixSuggestion', back_populates='user', cascade='all, delete-orphan'
    )

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    date = Column(Date, nullable=False)
    description = Column(String)
    usage = Column(String)
    amount = Column(Float)
    paid = Column(Boolean, default=True)
    recurring_id = Column(
        Integer,
        ForeignKey('recurring_entries.id', ondelete='CASCADE'),
        nullable=True
    )

    user = relationship('User', back_populates='transactions')
    recurring_entry = relationship(
        'RecurringEntry', back_populates='transactions'
    )

class RecurringEntry(Base):
    __tablename__ = 'recurring_entries'
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    description = Column(String)
    usage = Column(String)
    amount = Column(Float)
    duration = Column(Integer)
    start_date = Column(Date)

    user = relationship('User', back_populates='recurring_entries')
    transactions = relationship(
        'Transaction', back_populates='recurring_entry',
        cascade='all, delete'
    )

class FixSuggestion(Base):
    __tablename__ = 'fix_suggestions'
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True
    )
    description = Column(String, primary_key=True)
    usage = Column(String, primary_key=True)

    user = relationship('User', back_populates='fix_suggestions')
