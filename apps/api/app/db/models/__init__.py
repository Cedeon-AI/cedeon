"""ORM models. Import every model here so Alembic autogenerate sees full metadata."""

from app.db.base import Base
from app.db.models.audit import AuditEvent
from app.db.models.documents import Document, DocumentChunk, DocumentPage, DocumentParse
from app.db.models.extraction import (
    AgentRun,
    Citation,
    PromptVersion,
    Review,
    ToolCall,
    TreatyTermCandidate,
)
from app.db.models.identity import (
    Invitation,
    Membership,
    Organization,
    User,
    UserSession,
)
from app.db.models.losses import (
    LossEvent,
    LossImport,
    LossImportRow,
    UnderlyingLoss,
)
from app.db.models.recoveries import (
    Recoverable,
    RecoveryAllocation,
    RecoveryCalculation,
    RecoveryCandidate,
    RecoveryInvestigation,
    RecoveryInvestigationFinding,
    RecoveryNotice,
    RecoveryPacket,
    RecoveryPacketVersion,
)
from app.db.models.reinsurance import (
    Cedent,
    ReinsuranceProgram,
    Reinsurer,
    Treaty,
    TreatyLayer,
    TreatyParticipation,
    TreatyTerm,
    TreatyVersion,
)

__all__ = [
    "AgentRun",
    "AuditEvent",
    "Base",
    "Cedent",
    "Citation",
    "Document",
    "DocumentChunk",
    "DocumentPage",
    "DocumentParse",
    "Invitation",
    "LossEvent",
    "LossImport",
    "LossImportRow",
    "Membership",
    "Organization",
    "PromptVersion",
    "Recoverable",
    "RecoveryAllocation",
    "RecoveryCalculation",
    "RecoveryCandidate",
    "RecoveryInvestigation",
    "RecoveryInvestigationFinding",
    "RecoveryNotice",
    "RecoveryPacket",
    "RecoveryPacketVersion",
    "ReinsuranceProgram",
    "Reinsurer",
    "Review",
    "ToolCall",
    "Treaty",
    "TreatyLayer",
    "TreatyParticipation",
    "TreatyTerm",
    "TreatyTermCandidate",
    "TreatyVersion",
    "UnderlyingLoss",
    "User",
    "UserSession",
]
