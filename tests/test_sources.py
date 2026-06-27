import pytest

from src.models.job import Job
from src.sources.base import Source
from src.sources.greenhouse import GreenhouseSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
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


class MockGreenhouseBrowserEngine:
    def __init__(self):
        self.navigated_url = None

    async def navigate(self, url: str) -> None:
        self.navigated_url = url

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        pass

    async def evaluate(self, expression: str) -> object:
        return [
            {
                "title": "Frontend Engineer",
                "location": "New York",
                "url": "https://boards.greenhouse.io/testco/jobs/1",
                "department": "Engineering",
            },
            {
                "title": "Data Analyst",
                "location": "Remote",
                "url": "https://boards.greenhouse.io/testco/jobs/2",
                "department": "Data",
            },
        ]

    async def screenshot(self, path: str) -> None:
        pass


class TestGreenhouseSource:
    @pytest.mark.asyncio
    async def test_discover_returns_normalized_jobs(self):
        browser = MockGreenhouseBrowserEngine()
        source = GreenhouseSource(browser, board_slugs=["testco"])

        jobs = await source.discover()

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)

        job = jobs[0]
        assert job.source == "greenhouse"
        assert job.company == "Testco"
        assert job.title == "Frontend Engineer"
        assert job.location == "New York"
        assert job.apply_url == "https://boards.greenhouse.io/testco/jobs/1"

    @pytest.mark.asyncio
    async def test_discover_navigates_to_board(self):
        browser = MockGreenhouseBrowserEngine()
        source = GreenhouseSource(browser, board_slugs=["testco"])

        await source.discover()

        assert "boards.greenhouse.io/testco" in browser.navigated_url

    @pytest.mark.asyncio
    async def test_discover_returns_empty_with_no_slugs(self):
        browser = MockGreenhouseBrowserEngine()
        source = GreenhouseSource(browser, board_slugs=[])

        jobs = await source.discover()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_discover_handles_empty_results(self):
        class EmptyBrowser:
            async def navigate(self, url: str) -> None:
                pass
            async def wait_for(self, selector: str, timeout: int | None = None) -> None:
                pass
            async def evaluate(self, expression: str) -> object:
                return []
            async def screenshot(self, path: str) -> None:
                pass

        source = GreenhouseSource(EmptyBrowser(), board_slugs=["empty"])
        jobs = await source.discover()
        assert jobs == []


class MockLeverBrowserEngine:
    def __init__(self):
        self.navigated_url = None

    async def navigate(self, url: str) -> None:
        self.navigated_url = url

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        pass

    async def evaluate(self, expression: str) -> object:
        return [
            {"title": "Backend Engineer", "team": "Platform", "location": "SF", "url": "https://jobs.lever.co/testco/abc123"},
            {"title": "Product Manager", "team": "Product", "location": "Remote", "url": "https://jobs.lever.co/testco/def456"},
        ]

    async def screenshot(self, path: str) -> None:
        pass


class TestLeverSource:
    @pytest.mark.asyncio
    async def test_discover_returns_normalized_jobs(self):
        browser = MockLeverBrowserEngine()
        source = LeverSource(browser, company_slugs=["testco"])

        jobs = await source.discover()

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)

        job = jobs[0]
        assert job.source == "lever"
        assert job.company == "Testco"
        assert job.title == "Backend Engineer"
        assert job.location == "SF"
        assert job.apply_url == "https://jobs.lever.co/testco/abc123"

    @pytest.mark.asyncio
    async def test_discover_navigates_to_company(self):
        browser = MockLeverBrowserEngine()
        source = LeverSource(browser, company_slugs=["testco"])

        await source.discover()

        assert "jobs.lever.co/testco" in browser.navigated_url

    @pytest.mark.asyncio
    async def test_discover_returns_empty_with_no_slugs(self):
        browser = MockLeverBrowserEngine()
        source = LeverSource(browser, company_slugs=[])

        jobs = await source.discover()

        assert jobs == []


class MockLinkedInBrowserEngine:
    def __init__(self):
        self.navigated_url = None

    async def navigate(self, url: str) -> None:
        self.navigated_url = url

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        pass

    async def evaluate(self, expression: str) -> object:
        return [
            {"title": "ML Engineer", "company": "AI Corp", "location": "London", "url": "https://linkedin.com/jobs/view/123"},
            {"title": "DevOps Engineer", "company": "Cloud Inc", "location": "Berlin", "url": None},
        ]

    async def screenshot(self, path: str) -> None:
        pass


class TestLinkedInSource:
    @pytest.mark.asyncio
    async def test_discover_returns_normalized_jobs(self):
        browser = MockLinkedInBrowserEngine()
        source = LinkedInSource(browser, keywords=["python"])

        jobs = await source.discover()

        assert len(jobs) == 2
        assert all(isinstance(j, Job) for j in jobs)

        job = jobs[0]
        assert job.source == "linkedin"
        assert job.company == "AI Corp"
        assert job.title == "ML Engineer"
        assert job.location == "London"
        assert job.apply_url == "https://linkedin.com/jobs/view/123"

    @pytest.mark.asyncio
    async def test_discover_navigates_to_search(self):
        browser = MockLinkedInBrowserEngine()
        source = LinkedInSource(browser, keywords=["python"])

        await source.discover()

        assert "linkedin.com/jobs/search/" in browser.navigated_url
        assert "keywords=python" in browser.navigated_url

    @pytest.mark.asyncio
    async def test_discover_returns_empty_with_no_keywords(self):
        browser = MockLinkedInBrowserEngine()
        source = LinkedInSource(browser, keywords=[])

        jobs = await source.discover()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_discover_skips_invalid_jobs(self):
        browser = MockLinkedInBrowserEngine()

        async def evaluate_override(_expr: str) -> object:
            return [
                {"title": "", "company": "", "location": None, "url": None},
                {"title": "Valid", "company": "Co", "location": "NY", "url": "https://linkedin.com/jobs/view/1"},
            ]

        browser.evaluate = evaluate_override  # type: ignore[assignment]
        source = LinkedInSource(browser, keywords=["test"])

        jobs = await source.discover()

        assert len(jobs) == 1
        assert jobs[0].title == "Valid"
