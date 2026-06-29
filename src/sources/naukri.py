from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.config import SearchConfig
from src.models import JobListing


class NaukriSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        kw_slug = config.keywords.replace(" ", "-").lower()
        base = f"https://www.naukri.com/{kw_slug}-jobs"
        params: dict[str, str] = {"k": config.keywords}
        if config.naukri_experience:
            params["experience"] = config.naukri_experience
        if config.naukri_salary_lakhs:
            params["ctcFilter"] = config.naukri_salary_lakhs
        if config.remote_only:
            params["wfhType"] = "1"
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        url = NaukriSource.build_url(config)
        print(f"  Naukri: {url[:90]}...")

        jobs: list[JobListing] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as client:
                resp = await client.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    print(f"    Naukri returned {resp.status_code}")
                    return jobs

                text = resp.text
                soup = BeautifulSoup(text, "html.parser")

                # Try multiple container selectors
                listings = (
                    soup.select(".srp-jobtuple-wrapper")
                    or soup.select("article.jobTuple")
                    or soup.select("div.jobTuple")
                    or soup.select("[data-job-id]")
                    or soup.select("div.list")
                    or soup.select("div.job")
                )

                print(f"    Found {len(listings)} listings")

                if not listings:
                    # Debug: print first 800 chars of body so you can see what arrived
                    print(f"    DEBUG HTML snippet: {text[:800]}")

                for listing in listings[:config.max_jobs_per_source]:
                    try:
                        title_el = (
                            listing.select_one("a.title")
                            or listing.select_one("a.srp-jd-p-title")
                            or listing.select_one("h2 a")
                            or listing.select_one("a[class*='title']")
                        )
                        company_el = (
                            listing.select_one("a.comp-name")
                            or listing.select_one("a[href*='/company/']")
                            or listing.select_one("div.company-name")
                            or listing.select_one("[class*='company']")
                        )
                        loc_el = (
                            listing.select_one("span.locWdth")
                            or listing.select_one("span.location")
                            or listing.select_one("div.location")
                            or listing.select_one("[class*='loc']")
                        )
                        desc_el = (
                            listing.select_one("span.job-desc")
                            or listing.select_one("[class*='desc']")
                        )
                        salary_el = (
                            listing.select_one("span.sal")
                            or listing.select_one("span.salary")
                            or listing.select_one("[class*='salary']")
                        )
                        exp_el = (
                            listing.select_one("span.expwdth")
                            or listing.select_one("span.exp")
                            or listing.select_one("[class*='exp']")
                        )

                        title = title_el.get_text(strip=True) if title_el else ""
                        href = title_el.get("href") if title_el else ""
                        company = company_el.get_text(strip=True) if company_el else ""
                        location = loc_el.get_text(strip=True) if loc_el else ""
                        description = desc_el.get_text(strip=True) if desc_el else ""
                        salary = salary_el.get_text(strip=True) if salary_el else ""
                        exp = exp_el.get_text(strip=True) if exp_el else ""

                        if title and href:
                            full_url = (
                                href
                                if href.startswith("http")
                                else f"https://www.naukri.com{href}"
                            )
                            jobs.append(
                                JobListing(
                                    title=title,
                                    company=company,
                                    location=(location or exp),
                                    url=full_url,
                                    salary=salary if salary else None,
                                    description=description,
                                    source="naukri",
                                )
                            )
                    except Exception:
                        continue

                print(f"    {len(jobs)} Naukri jobs")

        except Exception as e:
            print(f"    Naukri error: {e}")

        return jobs
