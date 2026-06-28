"""Tests for form filler."""

from unittest.mock import MagicMock

import pytest

from src.screen.form_detector import FormDetector
from src.screen.form_filler import FormFiller
from src.screen.models import DetectedField, FieldType


@pytest.fixture
def mock_reader():
    return MagicMock()


@pytest.fixture
def mock_detector():
    return MagicMock(spec=FormDetector)


@pytest.fixture
def filler(mock_reader, mock_detector):
    return FormFiller(mock_reader, mock_detector)


class TestFormFiller:
    def test_initialization(self, mock_reader, mock_detector):
        filler = FormFiller(mock_reader, mock_detector)
        assert filler._reader == mock_reader
        assert filler._detector == mock_detector

    def test_fill_text_field_success(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextField",
            title="Email",
            field_type=FieldType.EMAIL,
            element_ref=MagicMock(),
        )
        mock_reader.focus_element.return_value = True
        mock_reader.set_value.return_value = True

        result = filler.fill_field(field, "test@example.com")
        assert result is True
        mock_reader.focus_element.assert_called_once_with(field.element_ref)
        mock_reader.set_value.assert_called_once_with(field.element_ref, "test@example.com")

    def test_fill_text_field_fallback_to_keyboard(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextField",
            title="Email",
            field_type=FieldType.TEXT,
            element_ref=MagicMock(),
        )
        mock_reader.focus_element.return_value = True
        mock_reader.set_value.return_value = False

        result = filler.fill_field(field, "test value")
        assert result is True
        mock_reader.perform_action.assert_called_once_with(field.element_ref, "AXPress")
        mock_reader.type_text.assert_called_once_with("test value")

    def test_fill_textarea(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextArea",
            title="Cover Letter",
            field_type=FieldType.TEXTAREA,
            element_ref=MagicMock(),
        )
        mock_reader.focus_element.return_value = True
        mock_reader.set_value.return_value = True

        result = filler.fill_field(field, "My cover letter text")
        assert result is True

    def test_fill_checkbox_checked(self, filler, mock_reader):
        field = DetectedField(
            role="AXCheckBox",
            title="Agree to terms",
            field_type=FieldType.CHECKBOX,
            element_ref=MagicMock(),
        )
        mock_reader.get_attribute.return_value = False
        mock_reader.click_element.return_value = True

        result = filler.fill_field(field, "true")
        assert result is True
        mock_reader.click_element.assert_called_once_with(field.element_ref)

    def test_fill_checkbox_unchecked(self, filler, mock_reader):
        field = DetectedField(
            role="AXCheckBox",
            title="Agree to terms",
            field_type=FieldType.CHECKBOX,
            element_ref=MagicMock(),
        )
        mock_reader.get_attribute.return_value = True
        mock_reader.click_element.return_value = True

        result = filler.fill_field(field, "false")
        assert result is True
        mock_reader.click_element.assert_called_once_with(field.element_ref)

    def test_fill_dropdown(self, filler, mock_reader):
        field = DetectedField(
            role="AXComboBox",
            title="Experience Level",
            field_type=FieldType.SELECT,
            element_ref=MagicMock(),
        )
        mock_reader.click_element.return_value = True

        child = MagicMock()
        mock_reader.get_children.return_value = [child]
        mock_reader.get_attribute.return_value = "Senior"

        result = filler.fill_field(field, "Senior")
        assert result is True

    def test_fill_field_no_element_ref(self, filler):
        field = DetectedField(
            role="AXTextField",
            title="Email",
            field_type=FieldType.TEXT,
            element_ref=None,
        )

        result = filler.fill_field(field, "test")
        assert result is False

    def test_find_value_for_field_standard(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Email")
        mock_detector.map_to_standard_field.return_value = "email"
        values = {"email": "test@example.com", "phone": "123-456-7890"}

        result = filler._find_value_for_field(field, values)
        assert result == "test@example.com"

    def test_find_value_for_field_by_title(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Custom Field")
        mock_detector.map_to_standard_field.return_value = None
        values = {"Custom Field": "custom value"}

        result = filler._find_value_for_field(field, values)
        assert result == "custom value"

    def test_find_value_for_field_not_found(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Unknown")
        mock_detector.map_to_standard_field.return_value = None
        values = {"email": "test@example.com"}

        result = filler._find_value_for_field(field, values)
        assert result is None

    def test_fill_all_fields(self, filler, mock_detector):
        fields = [
            DetectedField(
                role="AXTextField", title="Email",
                field_type=FieldType.EMAIL, element_ref=MagicMock()
            ),
            DetectedField(
                role="AXTextField", title="Phone",
                field_type=FieldType.PHONE, element_ref=MagicMock()
            ),
        ]
        mock_detector.map_to_standard_field.side_effect = ["email", "phone"]
        values = {"email": "test@example.com", "phone": "123-456-7890"}

        filler._reader.focus_element.return_value = True
        filler._reader.set_value.return_value = True

        success, fail = filler.fill_all_fields(fields, values)
        assert success == 2
        assert fail == 0
