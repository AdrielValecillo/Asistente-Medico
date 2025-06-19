from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ReportBase(BaseModel):
    report_content: str

class ReportCreate(ReportBase):
    pass

class Report(ReportBase):
    id: int
    user_id: int
    created_at: datetime
    file_hash: str

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    cedula: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    full_name: str

class User(UserBase):
    id: int
    full_name: str
    created_at: datetime
    reports: List[Report] = []

    class Config:
        from_attributes = True 