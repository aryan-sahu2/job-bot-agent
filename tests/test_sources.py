import pytest

from src.models.job import Job
from src.sources.base import Source
from src.sources.wellfound import WellfoundSource


class TestSourceInterface:
    def test_cannot_instantiate_abstract_source(self):
        with pytest.raises(TypeError):
            Source()  # type: ignore[abstract]


class MockBrowserEngine:
    def __init__(self):
        self.navigated_url = None
        self.waited_selector = None
        self.screenshot_path = None

    async def navigate(self, url: str) -> None:
        self.navigated_url = url

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        self.waited_selector = selector

    async def evaluate(self, expression: str) -> object:
        return [
            {
                "title": "Software Engineer",
                "company": "Test Corp",
                "location": "San Francisco",
                "salary": "$150k-$200k",
                "description": "We are hiring a software engineer.",
                "url": "https://wellfound.com/jobs/123",
            },
            {
                "title": "Backend Developer",
                "company": "Startup Inc",
                "location": "Remote",
                "salary": None,
                "description": "Backend role with Python.",
                "url": None,
            },
        ]

    async def screenshot(self, path: str) -> None:
        self.screenshot_path = path

    async def close(self) -> None:
        pass


class MockFailingBrowserEngine:
    async def navigate(self, url: str) -> None:
        raise Exception("Network error")

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        pass

    async def evaluate(self, expression: str) -> object:
        return []

    async def screenshot(self, path: str) -> None:
        pass

    async def close(self) -> None:
        pass


class MockEmptyBrowserEngine:
    async def navigate(self, url: str) -> None:
        pass

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        pass

    async def evaluate(self, expression: str) -> object:
        return []

    async def screenshot(self, path: str) -> None:
        pass

    async def close(self) -> None:
        pass


class TestWellfoundSource:
    @pytest.mark.asyncio
    async def test_discover_returns_normalized_jobs(self):
        browser = MockBrowserEngine()
        source = WellfoundSource(browser)

        jobs = await source.discover()

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)

        job = jobs[0]
        assert job.source == "wellfound"
        assert job.company == "Test Corp"
        assert job.title == "Software Engineer"
        assert job.location == "San Francisco"
        assert job.salary == "$150k-$200k"
        assert job.apply_url == "https://wellfound.com/jobs/123"

    @pytest.mark.asyncio
    async def test_discover_navigates_to_wellfound(self):
        browser = MockBrowserEngine()
        source = WellfoundSource(browser)

        await source.discover()

        assert "wellfound.com/jobs" in browser.navigated_url

    @pytest.mark.asyncio
    async def test_discover_returns_empty_on_failure(self):
        browser = MockFailingBrowserEngine()
        source = WellfoundSource(browser)

        jobs = await source.discover()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_discover_handles_empty_results(self):
        browser = MockEmptyBrowserEngine()
        source = WellfoundSource(browser)

        jobs = await source.discover()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_jobs(self):
        browser = MockBrowserEngine()

        async def evaluate_override(_expr: str) -> object:
            return [
                {"title": "", "company": "", "description": "bad"},
                {"title": "Valid", "company": "Co", "description": "good"},
            ]

        browser.evaluate = evaluate_override  # type: ignore[assignment]
        source = WellfoundSource(browser)

        jobs = await source.discover()

        assert len(jobs) == 1
        assert jobs[0].title == "Valid"
