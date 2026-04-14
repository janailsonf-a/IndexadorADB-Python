from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FileMetadataUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    campaign: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, max_length=50)
    is_official: Optional[bool] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class FileMetadataResponse(BaseModel):
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    campaign: Optional[str] = None
    status: Optional[str] = None
    is_official: bool = False
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)