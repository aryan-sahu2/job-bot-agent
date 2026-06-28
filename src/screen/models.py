"""Screen-specific data models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FieldType(str, Enum):
    """Detected form field types."""

    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    TEXTAREA = "textarea"
    SELECT = "select"
    FILE = "file"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    URL = "url"
    DATE = "date"
    UNKNOWN = "unknown"


class DetectedField(BaseModel):
    """A form field detected via accessibility APIs."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: str = Field(description="AXRole of the element (e.g., AXTextField, AXTextArea)")
    title: str = Field(default="", description="AXTitle attribute")
    description: str = Field(default="", description="AXDescription attribute")
    value: str = Field(default="", description="Current AXValue")
    identifier: str = Field(default="", description="AXIdentifier attribute")
    field_type: FieldType = Field(default=FieldType.UNKNOWN, description="Mapped field type")
    element_ref: Any = Field(default=None, description="AXUIElement reference (not serialized)")
    required: bool = Field(default=False, description="Whether field is required")


class ScreenJob(BaseModel):
    """Job information extracted from the current screen."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = Field(default="", description="Job title")
    company: str = Field(default="", description="Company name")
    location: str = Field(default="", description="Job location")
    description: str = Field(default="", description="Full job description text")
    requirements: list[str] = Field(default_factory=list, description="Extracted requirements")
    url: str = Field(default="", description="Current page URL")


class ApplyButton(BaseModel):
    """A detected Apply/Submit button."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    role: str = Field(description="AXRole of the button")
    title: str = Field(default="", description="AXTitle (button text)")
    description: str = Field(default="", description="AXDescription")
    element_ref: Any = Field(default=None, description="AXUIElement reference")


class WorkflowState(str, Enum):
    """Current state of the screen workflow."""

    IDLE = "idle"
    SCANNING = "scanning"
    READING_JOB = "reading_job"
    GENERATING_ANSWERS = "generating_answers"
    CLICKING_APPLY = "clicking_apply"
    DETECTING_FIELDS = "detecting_fields"
    FILLING_FIELDS = "filling_fields"
    AWAITING_DECISION = "awaiting_decision"
    SUBMITTING = "submitting"
    COMPLETE = "complete"
    ERROR = "error"
