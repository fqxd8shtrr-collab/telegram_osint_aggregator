from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, Index
from datetime import datetime
import config

Base = declarative_base()

class SourceChannel(Base):
    __tablename__ = "source_channels"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    title = Column(String)
    enabled = Column(Boolean, default=True)
    label = Column(String)
    category = Column(String)          # e.g., military, political
    trust_score = Column(Float, default=1.0)
    speed_score = Column(Float, default=1.0)
    priority_score = Column(Float, default=1.0)
    target_outputs = Column(JSON)      # list of output channel IDs
    video_only = Column(Boolean, default=False)  # if only videos should be sent from this source
    created_at = Column(DateTime, default=datetime.utcnow)

class ForwardedMessage(Base):
    __tablename__ = "forwarded_messages"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False)
    source_channel_id = Column(Integer, ForeignKey("source_channels.id"))
    content_hash = Column(String, index=True)
    normalized_text_hash = Column(String, index=True)
    text = Column(Text)
    language = Column(String, default="unknown")
    has_media = Column(Boolean, default=False)
    media_type = Column(String)  # photo, video, document, audio
    processed_at = Column(DateTime, default=datetime.utcnow)
    sent_to = Column(JSON)  # list of output channels it was sent to

class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("forwarded_messages.id"))
    importance_score = Column(Float)
    urgency_score = Column(Float)
    confidence_score = Column(Float)
    event_type = Column(String)
    summary = Column(Text)
    translated_text = Column(Text)
    deep_analysis = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class EventCluster(Base):
    __tablename__ = "event_clusters"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    importance_score = Column(Float)
    urgency_score = Column(Float)
    confidence_score = Column(Float)
    status = Column(String, default="active")  # active, resolved
    created_at = Column(DateTime, default=datetime.utcnow)

class ClusterMessage(Base):
    __tablename__ = "cluster_messages"
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey("event_clusters.id"))
    message_id = Column(Integer, ForeignKey("forwarded_messages.id"))
    added_at = Column(DateTime, default=datetime.utcnow)

class OutputTarget(Base):
    __tablename__ = "output_targets"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)  # channel ID
    username = Column(String)
    title = Column(String)
    enabled = Column(Boolean, default=True)
    description = Column(String)
    video_only = Column(Boolean, default=False)  # if this target receives only videos
    created_at = Column(DateTime, default=datetime.utcnow)

class RoutingRule(Base):
    __tablename__ = "routing_rules"
    id = Column(Integer, primary_key=True)
    source_channel_id = Column(Integer, ForeignKey("source_channels.id"))
    output_target_id = Column(Integer, ForeignKey("output_targets.id"))
    condition = Column(JSON)  # e.g., {"event_type": "military", "min_importance": 0.8}

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    role = Column(String, default="monitor")  # admin, analyst, editor, monitor
    created_at = Column(DateTime, default=datetime.utcnow)

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("forwarded_messages.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="new")  # new, under_review, confirmed, published, rejected
    assigned_at = Column(DateTime, default=datetime.utcnow)

class InternalComment(Base):
    __tablename__ = "internal_comments"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("forwarded_messages.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class BotState(Base):
    __tablename__ = "bot_state"
    key = Column(String, primary_key=True)
    value = Column(Text)

class ErrorLog(Base):
    __tablename__ = "error_logs"
    id = Column(Integer, primary_key=True)
    module = Column(String)
    error = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class HealthLog(Base):
    __tablename__ = "health_logs"
    id = Column(Integer, primary_key=True)
    component = Column(String)
    status = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create indexes
Index('idx_forwarded_messages_content_hash', ForwardedMessage.content_hash)
Index('idx_forwarded_messages_normalized_text_hash', ForwardedMessage.normalized_text_hash)
Index('idx_forwarded_messages_processed_at', ForwardedMessage.processed_at)
Index('idx_ai_evaluations_message_id', AIEvaluation.message_id)
Index('idx_event_clusters_start_time', EventCluster.start_time)

# Database engine and session
engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
