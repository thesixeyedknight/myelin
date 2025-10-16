from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Any


class Plan(BaseModel):
    steps: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class Evidence(BaseModel):
    notes: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)  # PMIDs etc.
    artifacts: Dict[str, str] = Field(default_factory=dict)  # name -> path
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
