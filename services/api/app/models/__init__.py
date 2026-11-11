"""Import all models so Base.metadata / Alembic autogenerate sees them."""
from app.models.agent import AgentExecution, AgentToolLog
from app.models.ai import AiConversation, AiMessage
from app.models.audit import AuditLog, Notification
from app.models.inspection import DetectedDefect, Inspection, InspectionImage
from app.models.knowledge import Document, DocumentChunk
from app.models.machine import Machine, SensorReading
from app.models.maintenance import MaintenancePrediction, MaintenanceRequest
from app.models.mlops import MLModel, MLModelVersion, ModelMetric
from app.models.mlops_datasets import MLDataset, MLExperiment
from app.models.organization import Organization
from app.models.user import User

__all__ = [
    "Organization", "User",
    "Machine", "SensorReading",
    "Inspection", "InspectionImage", "DetectedDefect",
    "MaintenancePrediction", "MaintenanceRequest",
    "Document", "DocumentChunk",
    "AiConversation", "AiMessage",
    "AgentExecution", "AgentToolLog",
    "MLDataset", "MLExperiment", "MLModel", "MLModelVersion", "ModelMetric",
    "AuditLog", "Notification",
]
