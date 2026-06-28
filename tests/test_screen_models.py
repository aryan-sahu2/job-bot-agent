"""Tests for screen module models."""

from src.screen.models import (
    ApplyButton,
    DetectedField,
    FieldType,
    ScreenJob,
    WorkflowState,
)


def test_field_type_enum():
    assert FieldType.TEXT == "text"
    assert FieldType.EMAIL == "email"
    assert FieldType.PHONE == "phone"
    assert FieldType.NAME == "name"
    assert FieldType.TEXTAREA == "textarea"
    assert FieldType.SELECT == "select"
    assert FieldType.FILE == "file"
    assert FieldType.CHECKBOX == "checkbox"
    assert FieldType.RADIO == "radio"
    assert FieldType.URL == "url"
    assert FieldType.DATE == "date"
    assert FieldType.UNKNOWN == "unknown"


def test_detected_field_defaults():
    field = DetectedField(role="AXTextField")
    assert field.role == "AXTextField"
    assert field.title == ""
    assert field.description == ""
    assert field.value == ""
    assert field.identifier == ""
    assert field.field_type == FieldType.UNKNOWN
    assert field.element_ref is None
    assert field.required is False


def test_detected_field_with_values():
    field = DetectedField(
        role="AXTextField",
        title="Email",
        description="Your email address",
        value="test@example.com",
        identifier="email-field",
        field_type=FieldType.EMAIL,
        required=True,
    )
    assert field.title == "Email"
    assert field.field_type == FieldType.EMAIL
    assert field.required is True


def test_screen_job_defaults():
    job = ScreenJob()
    assert job.title == ""
    assert job.company == ""
    assert job.location == ""
    assert job.description == ""
    assert job.requirements == []
    assert job.url == ""


def test_screen_job_with_values():
    job = ScreenJob(
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        description="Build amazing things",
        requirements=["Python", "TypeScript"],
        url="https://example.com/job",
    )
    assert job.title == "Software Engineer"
    assert job.company == "Tech Corp"
    assert len(job.requirements) == 2


def test_apply_button():
    button = ApplyButton(
        role="AXButton",
        title="Apply Now",
        description="Click to apply",
    )
    assert button.role == "AXButton"
    assert button.title == "Apply Now"
    assert button.element_ref is None


def test_workflow_state_enum():
    assert WorkflowState.IDLE == "idle"
    assert WorkflowState.SCANNING == "scanning"
    assert WorkflowState.READING_JOB == "reading_job"
    assert WorkflowState.GENERATING_ANSWERS == "generating_answers"
    assert WorkflowState.CLICKING_APPLY == "clicking_apply"
    assert WorkflowState.DETECTING_FIELDS == "detecting_fields"
    assert WorkflowState.FILLING_FIELDS == "filling_fields"
    assert WorkflowState.AWAITING_DECISION == "awaiting_decision"
    assert WorkflowState.SUBMITTING == "submitting"
    assert WorkflowState.COMPLETE == "complete"
    assert WorkflowState.ERROR == "error"
