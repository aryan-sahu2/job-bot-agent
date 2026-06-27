from pathlib import Path
from string import Template


class PromptLoader:
    def __init__(self, prompts_dir: str | Path = "prompts"):
        self._prompts_dir = Path(prompts_dir)

    def load(self, template_name: str) -> str:
        path = self._resolve(template_name)
        return path.read_text(encoding="utf-8")

    def render(self, template_name: str, **kwargs) -> str:
        template_str = self.load(template_name)
        template = Template(template_str)
        return template.safe_substitute(**kwargs)

    def list_templates(self) -> list[str]:
        if not self._prompts_dir.exists():
            return []
        return sorted(p.stem for p in self._prompts_dir.iterdir() if p.suffix == ".md")

    def _resolve(self, template_name: str) -> Path:
        path = self._prompts_dir / template_name
        if not path.suffix:
            path = path.with_suffix(".md")
        if not path.exists():
            msg = f"Prompt template not found: {path}"
            raise FileNotFoundError(msg)
        return path
