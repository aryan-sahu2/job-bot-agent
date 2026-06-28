"""Tests for form detector."""

from unittest.mock import MagicMock

import pytest

from src.screen.form_detector import FormDetector
from src.screen.models import DetectedField, FieldType


@pytest.fixture
def mock_reader():
    return MagicMock()


@pytest.fixture
def detector(mock_reader):
    return FormDetector(mock_reader)


class TestFormDetector:
    def test_initialization(self, mock_reader):
        detector = FormDetector(mock_reader)
        assert detector._reader == mock_reader

    def test_map_to_standard_field_email(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="Email Address",
            description="Your email",
        )
        result = detector.map_to_standard_field(field)
        assert result == "email"

    def test_map_to_standard_field_phone(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="Phone Number",
            description="Contact number",
        )
        result = detector.map_to_standard_field(field)
        assert result == "phone"

    def test_map_to_standard_field_first_name(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="First Name",
        )
        result = detector.map_to_standard_field(field)
        assert result == "first_name"

    def test_map_to_standard_field_last_name(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="Last Name",
        )
        result = detector.map_to_standard_field(field)
        assert result == "last_name"

    def test_map_to_standard_field_resume(self, detector):
        field = DetectedField(
            role="AXButton",
            title="Upload Resume",
        )
        result = detector.map_to_standard_field(field)
        assert result == "resume"

    def test_map_to_standard_field_linkedin(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="LinkedIn URL",
        )
        result = detector.map_to_standard_field(field)
        assert result == "linkedin"

    def test_map_to_standard_field_github(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="GitHub Profile",
        )
        result = detector.map_to_standard_field(field)
        assert result == "github"

    def test_map_to_standard_field_website(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="Portfolio Website",
        )
        result = detector.map_to_standard_field(field)
        assert result == "website"

    def test_map_to_standard_field_custom(self, detector):
        field = DetectedField(
            role="AXTextField",
            title="What is your favorite color?",
        )
        result = detector.map_to_standard_field(field)
        assert result is None

    def test_is_upload_field(self, detector):
        field = DetectedField(role="AXButton", field_type=FieldType.FILE)
        assert detector.is_upload_field(field) is True

    def test_is_not_upload_field(self, detector):
        field = DetectedField(role="AXTextField", field_type=FieldType.TEXT)
        assert detector.is_upload_field(field) is False

    def test_is_dropdown_field(self, detector):
        field = DetectedField(role="AXComboBox", field_type=FieldType.SELECT)
        assert detector.is_dropdown_field(field) is True

    def test_is_not_dropdown_field(self, detector):
        field = DetectedField(role="AXTextField", field_type=FieldType.TEXT)
        assert detector.is_dropdown_field(field) is False

    def test_get_required_fields(self, detector):
        fields = [
            DetectedField(role="AXTextField", required=True),
            DetectedField(role="AXTextField", required=False),
            DetectedField(role="AXTextField", required=True),
        ]
        required = detector.get_required_fields(fields)
        assert len(required) == 2

    def test_get_optional_fields(self, detector):
        fields = [
            DetectedField(role="AXTextField", required=True),
            DetectedField(role="AXTextField", required=False),
            DetectedField(role="AXTextField", required=True),
        ]
        optional = detector.get_optional_fields(fields)
        assert len(optional) == 1
