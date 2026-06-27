import pytest

from src.prompts.loader import PromptLoader


class TestPromptLoader:
    def test_load_existing_template(self):
        loader = PromptLoader()
        content = loader.load("answer_generation")
        assert isinstance(content, str)
        assert len(content) > 50
        assert "$title" in content
        assert "$company" in content

    def test_load_with_extension(self):
        loader = PromptLoader()
        content = loader.load("job_matching.md")
        assert "$company" in content
        assert "$description" in content

    def test_load_nonexistent_template(self):
        loader = PromptLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent_template")

    def test_render_substitutes_variables(self):
        loader = PromptLoader()
        result = loader.render("rewrite", current_answer="test", company="ACME")
        assert "test" in result
        assert "ACME" in result

    def test_render_missing_variable_uses_empty(self):
        loader = PromptLoader()
        result = loader.render("answer_generation", company="ACME", title="Engineer")
        assert "ACME" in result
        assert "Engineer" in result

    def test_render_with_all_expected_variables(self):
        loader = PromptLoader()
        result = loader.render(
            "answer_generation",
            company="ACME Corp",
            title="Senior Engineer",
            description="Build things.",
            name="Jane Doe",
            profile_title="Engineer",
            skills="Python, Go",
            experience="5 years at Tech Corp",
            education="BS CS",
            summary="Experienced builder.",
        )
        assert "ACME Corp" in result
        assert "Senior Engineer" in result
        assert "Jane Doe" in result
        assert "Python, Go" in result

    def test_list_templates(self):
        loader = PromptLoader()
        templates = loader.list_templates()
        assert "answer_generation" in templates
        assert "job_matching" in templates
        assert "rewrite" in templates

    def test_list_templates_empty_dir(self, tmp_path):
        loader = PromptLoader(prompts_dir=tmp_path)
        assert loader.list_templates() == []

    def test_load_and_render_are_independent(self):
        loader = PromptLoader()
        first = loader.render("rewrite", current_answer="v1", company="C1")
        second = loader.render("rewrite", current_answer="v2", company="C2")
        assert "v1" in first
        assert "v2" in second
        assert "C1" in first
        assert "C2" in second

    def test_load_from_custom_directory(self, tmp_path):
        custom_prompt = tmp_path / "test_prompt.md"
        custom_prompt.write_text("Hello $name")
        loader = PromptLoader(prompts_dir=tmp_path)
        result = loader.render("test_prompt", name="World")
        assert result == "Hello World"
