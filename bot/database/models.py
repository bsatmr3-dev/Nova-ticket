from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class PanelCategory:
    id: str
    name: str
    description: str
    emoji: str
    category_id: int
    naming_format: str = "ticket-{id}"
    support_role_ids: List[int] = field(default_factory=list)

@dataclass
class Panel:
    id: int
    title: str
    description: str
    color: int
    image_url: Optional[str] = None
    banner_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    footer_text: Optional[str] = None
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    categories: List[PanelCategory] = field(default_factory=list)

@dataclass
class Ticket:
    id: int
    guild_id: int
    channel_id: int
    user_id: int
    panel_id: int
    category_id: str
    status: str # 'open', 'closed', 'locked'
    claimed_by: Optional[int] = None
    priority: str = "Medium" # 'Low', 'Medium', 'High', 'Urgent'
    department: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    closed_at: Optional[str] = None
    first_response_at: Optional[str] = None

@dataclass
class Rating:
    ticket_id: int
    user_id: int
    staff_id: int
    stars: int # 1 to 5
    feedback: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class BlacklistEntry:
    user_id: int
    reason: str
    added_by: int
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class RoleHierarchyConfig:
    owner_role_id: Optional[int] = None
    admin_role_id: Optional[int] = None
    support_manager_role_id: Optional[int] = None
    senior_support_role_id: Optional[int] = None
    support_role_id: Optional[int] = None
