from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Knowledge(Base):
    """Store learned knowledge and facts"""
    __tablename__ = 'knowledge'
    
    id = Column(Integer, primary_key=True)
    topic = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(255))  # web, conversation, etc.
    confidence_score = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_verified = Column(Boolean, default=False)

class ConversationHistory(Base):
    """Store conversation history for learning"""
    __tablename__ = 'conversation_history'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    keywords = Column(Text)  # JSON string of extracted keywords
    sentiment_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearningPattern(Base):
    """Store learned conversation patterns"""
    __tablename__ = 'learning_patterns'
    
    id = Column(Integer, primary_key=True)
    pattern_type = Column(String(100), nullable=False)  # greeting, question, etc.
    trigger_words = Column(Text, nullable=False)  # JSON array
    responses = Column(Text, nullable=False)  # JSON array
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WebSource(Base):
    """Track web sources for knowledge"""
    __tablename__ = 'web_sources'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False, unique=True)
    title = Column(String(500))
    domain = Column(String(100), index=True)
    last_scraped = Column(DateTime)
    content_hash = Column(String(64))  # To detect changes
    is_active = Column(Boolean, default=True)
    scrape_frequency = Column(Integer, default=86400)  # seconds between scrapes
    created_at = Column(DateTime, default=datetime.utcnow)

class TopicKeyword(Base):
    """Map keywords to topics for better organization"""
    __tablename__ = 'topic_keywords'
    
    id = Column(Integer, primary_key=True)
    keyword = Column(String(100), nullable=False, index=True)
    topic = Column(String(255), nullable=False, index=True)
    frequency = Column(Integer, default=1)
    relevance_score = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)