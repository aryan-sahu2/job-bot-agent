"""Tests for form filler."""

from unittest.mock import AsyncMock

import pytest

from src.screen.form_detector import FormDetector
from src.screen.form_filler import FormFiller
from src.screen.models import DetectedField, FieldType


@pytest.fixture
def mock_reader():
    return AsyncMock()


@pytest.fixture
def mock_detector():
    return AsyncMock(spec=FormDetector)


@pytest.fixture
def filler(mock_reader, mock_detector):
    return FormFiller(mock_reader, mock_detector)


class TestFormFiller:
    @pytest.mark.asyncio
    async def test_initialization(self, mock_reader, mock_detector):
        filler = FormFiller(mock_reader, mock_detector)
        assert filler._reader == mock_reader
        assert filler._detector == mock_detector

    @pytest.mark.asyncio
    async def test_fill_text_field_success(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextField",
            title="Email",
            field_type=FieldType.EMAIL,
            identifier="#email",
        )

        result = await filler.fill_field(field, "test@example.com")
        assert result is True
        mock_reader.fill.assert_called_once_with("#email", "test@example.com")

    @pytest.mark.asyncio
    async def test_fill_textarea(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextArea",
            title="Cover Letter",
            field_type=FieldType.TEXTAREA,
            identifier="#cover",
        )

        result = await filler.fill_field(field, "My cover letter text")
        assert result is True
        mock_reader.fill.assert_called_once_with("#cover", "My cover letter text")

    @pytest.mark.asyncio
    async def test_fill_checkbox_checked(self, filler, mock_reader):
        field = DetectedField(
            role="AXCheckBox",
            title="Agree to terms",
            field_type=FieldType.CHECKBOX,
            identifier="#agree",
        )

        result = await filler.fill_field(field, "true")
        assert result is True
        mock_reader.check.assert_called_once_with("#agree", True)

    @pytest.mark.asyncio
    async def test_fill_checkbox_unchecked(self, filler, mock_reader):
        field = DetectedField(
            role="AXCheckBox",
            title="Agree to terms",
            field_type=FieldType.CHECKBOX,
            identifier="#agree",
        )

        result = await filler.fill_field(field, "false")
        assert result is True
        mock_reader.check.assert_called_once_with("#agree", False)

    @pytest.mark.asyncio
    async def test_fill_dropdown(self, filler, mock_reader):
        field = DetectedField(
            role="AXComboBox",
            title="Experience Level",
            field_type=FieldType.SELECT,
            identifier="#level",
        )

        result = await filler.fill_field(field, "Senior")
        assert result is True
        mock_reader.select.assert_called_once_with("#level", "Senior")

    @pytest.mark.asyncio
    async def test_fill_radio_selected(self, filler, mock_reader):
        field = DetectedField(
            role="AXRadioButton",
            title="Option A",
            field_type=FieldType.RADIO,
            identifier="#option-a",
        )

        result = await filler.fill_field(field, "true")
        assert result is True
        mock_reader.click.assert_called_once_with("#option-a")

    @pytest.mark.asyncio
    async def test_fill_radio_not_selected(self, filler, mock_reader):
        field = DetectedField(
            role="AXRadioButton",
            title="Option A",
            field_type=FieldType.RADIO,
            identifier="#option-a",
        )

        result = await filler.fill_field(field, "false")
        assert result is True

    @pytest.mark.asyncio
    async def test_fill_file_upload(self, filler, mock_reader):
        field = DetectedField(
            role="AXTextField",
            title="Upload CV",
            field_type=FieldType.FILE,
            identifier="#resume",
        )

        result = await filler.fill_field(field, "/path/to/resume.pdf")
        assert result is True
        mock_reader.upload.assert_called_once_with("#resume", "/path/to/resume.pdf")

    @pytest.mark.asyncio
    async def test_fill_field_no_identifier(self, filler):
        field = DetectedField(
            role="AXTextField",
            title="Email",
            field_type=FieldType.TEXT,
            identifier="",
        )

        result = await filler.fill_field(field, "test")
        assert result is False

    @pytest.mark.asyncio
    async def test_find_value_for_field_standard(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Email")
        mock_detector.map_to_standard_field.return_value = "email"
        values = {"email": "test@example.com", "phone": "123-456-7890"}

        result = filler._find_value_for_field(field, values)
        assert result == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_value_for_field_by_title(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Custom Field")
        mock_detector.map_to_standard_field.return_value = None
        values = {"Custom Field": "custom value"}

        result = filler._find_value_for_field(field, values)
        assert result == "custom value"

    @pytest.mark.asyncio
    async def test_find_value_for_field_not_found(self, filler, mock_detector):
        field = DetectedField(role="AXTextField", title="Unknown")
        mock_detector.map_to_standard_field.return_value = None
        values = {"email": "test@example.com"}

        result = filler._find_value_for_field(field, values)
        assert result is None

    @pytest.mark.asyncio
    async def test_find_value_for_field_by_type_email(self, filler, mock_detector):
        field = DetectedField(
            role="AXTextField",
            title="Enter your email address",
            field_type=FieldType.EMAIL,
        )
        mock_detector.map_to_standard_field.return_value = None
        values = {"email": "test@example.com"}

        result = filler._find_value_for_field(field, values)
        assert result == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_value_for_field_by_type_phone(self, filler, mock_detector):
        field = DetectedField(
            role="AXTextField",
            title="Contact number",
            field_type=FieldType.PHONE,
        )
        mock_detector.map_to_standard_field.return_value = None
        values = {"phone": "123-456-7890"}

        result = filler._find_value_for_field(field, values)
        assert result == "123-456-7890"

    @pytest.mark.asyncio
    async def test_find_value_for_field_by_type_website(self, filler, mock_detector):
        field = DetectedField(
            role="AXTextField",
            title="Portfolio URL",
            field_type=FieldType.URL,
        )
        mock_detector.map_to_standard_field.return_value = None
        values = {"website": "https://example.com"}

        result = filler._find_value_for_field(field, values)
        assert result == "https://example.com"

    @pytest.mark.asyncio
    async def test_find_value_for_field_by_type_resume(self, filler, mock_detector):
        field = DetectedField(
            role="AXTextField",
            title="Upload CV",
            field_type=FieldType.FILE,
        )
        mock_detector.map_to_standard_field.return_value = None
        values = {"resume": "/path/to/resume.pdf"}

        result = filler._find_value_for_field(field, values)
        assert result == "/path/to/resume.pdf"

    @pytest.mark.asyncio
    async def test_fill_all_fields(self, filler, mock_detector):
        fields = [
            DetectedField(
                role="AXTextField",
                title="Email",
                field_type=FieldType.EMAIL,
                identifier="#email",
            ),
            DetectedField(
                role="AXTextField",
                title="Phone",
                field_type=FieldType.PHONE,
                identifier="#phone",
            ),
        ]
        mock_detector.map_to_standard_field.side_effect = ["email", "phone"]

        success, fail = await filler.fill_all_fields(
            fields, {"email": "test@example.com", "phone": "123-456-7890"}
        )
        assert success == 2
        assert fail == 0

    @pytest.mark.asyncio
    async def test_fill_all_fields_no_values(self, filler, mock_detector):
        fields = [
            DetectedField(
                role="AXTextField",
                title="Email",
                field_type=FieldType.EMAIL,
                identifier="#email",
            ),
        ]
        mock_detector.map_to_standard_field.return_value = None

        success, fail = await filler.fill_all_fields(fields, {})
        assert success == 0
        assert fail == 0
