import pytest

from src.profile.manager import ProfileManager
from src.profile.models import Education, Experience, Profile, Resume
from src.profile.parser import ResumeParser

SAMPLE_RESUME = """Jane Doe
Senior Software Engineer
San Francisco, CA
jane@example.com
+1-555-123-4567

Professional Summary
Experienced software engineer with 8 years building scalable web applications.

Skills
Python, Go, TypeScript, Kubernetes, PostgreSQL, AWS

Experience
Tech Corp\tSenior Engineer\t2020-01 – Present
Led backend team building microservices architecture.
Improved API response times by 40%.
Mentored 4 junior engineers.

Startup Inc\tSoftware Engineer\t2017-03 – 2019-12
Built customer-facing features using Python and React.
Designed RESTful APIs serving 100k+ daily users.

Education
Bachelor of Science, Computer Science, MIT, 2016

Links
https://github.com/janedoe
https://linkedin.com/in/janedoe
"""


class TestProfileModels:
    def test_create_experience(self):
        exp = Experience(
            title="Senior Engineer",
            company="Tech Corp",
            start_date="2020-01",
            end_date="Present",
        )
        assert exp.title == "Senior Engineer"
        assert exp.company == "Tech Corp"
        assert exp.location is None

    def test_create_education(self):
        edu = Education(
            degree="Bachelor of Science",
            institution="MIT",
            field="Computer Science",
            graduation_year="2016",
        )
        assert edu.degree == "Bachelor of Science"
        assert edu.graduation_year == "2016"

    def test_create_profile(self):
        profile = Profile(
            name="Jane Doe",
            email="jane@example.com",
            skills=["Python", "Go"],
        )
        assert profile.name == "Jane Doe"
        assert profile.skills == ["Python", "Go"]
        assert profile.experience == []
        assert profile.education == []

    def test_create_resume(self):
        profile = Profile(name="Jane Doe", email="jane@example.com")
        resume = Resume(raw_text="resume text", profile=profile)
        assert resume.raw_text == "resume text"
        assert resume.profile.name == "Jane Doe"
        assert resume.file_path is None


class TestResumeParser:
    def test_parse_full_resume(self):
        parser = ResumeParser()
        profile = parser.parse(SAMPLE_RESUME)

        assert profile.name == "Jane Doe"
        assert profile.email == "jane@example.com"
        assert profile.phone == "+1-555-123-4567"
        assert profile.location == "San Francisco, CA"
        assert "Python" in profile.skills
        assert "Go" in profile.skills
        assert "Kubernetes" in profile.skills

    def test_parse_experience_section(self):
        parser = ResumeParser()
        profile = parser.parse(SAMPLE_RESUME)

        assert len(profile.experience) >= 1
        exp = profile.experience[0]
        assert exp.company == "Tech Corp"
        assert exp.title == "Senior Engineer"

    def test_parse_education_section(self):
        parser = ResumeParser()
        profile = parser.parse(SAMPLE_RESUME)

        assert len(profile.education) >= 1
        edu = profile.education[0]
        assert edu.degree == "Bachelor of Science"
        assert edu.institution == "MIT"

    def test_parse_summary_section(self):
        parser = ResumeParser()
        profile = parser.parse(SAMPLE_RESUME)

        assert profile.summary is not None
        assert "scalable web applications" in profile.summary

    def test_parse_urls(self):
        parser = ResumeParser()
        profile = parser.parse(SAMPLE_RESUME)

        assert len(profile.urls) >= 2
        assert any("github.com/janedoe" in url for url in profile.urls)
        assert any("linkedin.com/in/janedoe" in url for url in profile.urls)

    def test_parse_empty_text(self):
        parser = ResumeParser()
        profile = parser.parse("")

        assert profile.name == "Unknown"
        assert profile.email is None
        assert profile.skills == []

    def test_parse_minimal_text(self):
        parser = ResumeParser()
        profile = parser.parse("John Smith\njohn@email.com")

        assert profile.name == "John Smith"
        assert profile.email == "john@email.com"

    def test_parse_no_sections(self):
        parser = ResumeParser()
        text = "Alice\nEngineer\nalice@test.com\n(555) 123-4567"
        profile = parser.parse(text)

        assert profile.name == "Alice"
        assert profile.email == "alice@test.com"
        assert profile.phone is not None

    def test_parse_with_uppercase_section_headers(self):
        text = """Bob Smith
bob@example.com

SUMMARY
A good engineer.

SKILLS
Java, Spring, Docker

EXPERIENCE
Big Co\tLead Developer\t2019 – Present
Built critical systems.

EDUCATION
MSc, Computer Science, Stanford, 2018
"""
        parser = ResumeParser()
        profile = parser.parse(text)

        assert profile.name == "Bob Smith"
        assert "Java" in profile.skills
        assert profile.experience[0].company == "Big Co"
        assert profile.education[0].institution == "Stanford"

    def test_parse_contact_extraction(self):
        text = """Contact: Alex
Email: alex@corp.com
Phone: +1 (415) 555-0000
Location: New York, NY
"""
        parser = ResumeParser()
        profile = parser.parse(text)

        assert profile.email == "alex@corp.com"
        assert profile.phone is not None


class TestProfileManager:
    def test_load_resume_from_file(self, tmp_path):
        resume_file = tmp_path / "resume.txt"
        resume_file.write_text(SAMPLE_RESUME)

        manager = ProfileManager()
        resume = manager.load_resume(resume_file)

        assert isinstance(resume, Resume)
        assert resume.file_path == str(resume_file)
        assert resume.profile.name == "Jane Doe"
        assert resume.profile.email == "jane@example.com"

    def test_load_profile_from_resume(self, tmp_path):
        resume_file = tmp_path / "resume.txt"
        resume_file.write_text(SAMPLE_RESUME)

        manager = ProfileManager()
        profile = manager.load_profile_from_resume(resume_file)

        assert isinstance(profile, Profile)
        assert profile.name == "Jane Doe"
        assert profile.email == "jane@example.com"

    def test_load_resume_file_not_found(self):
        manager = ProfileManager()
        with pytest.raises(FileNotFoundError):
            manager.load_resume("/nonexistent/resume.txt")
