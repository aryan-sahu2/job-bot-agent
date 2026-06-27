from pathlib import Path

from src.profile.models import Profile, Resume
from src.profile.parser import ResumeParser


class ProfileManager:
    def __init__(self, parser: ResumeParser | None = None):
        self._parser = parser or ResumeParser()

    def load_resume(self, file_path: str | Path) -> Resume:
        path = Path(file_path)
        raw_text = path.read_text(encoding="utf-8")
        profile = self._parser.parse(raw_text)
        return Resume(raw_text=raw_text, profile=profile, file_path=str(path))

    def load_profile_from_resume(self, file_path: str | Path) -> Profile:
        resume = self.load_resume(file_path)
        return resume.profile
