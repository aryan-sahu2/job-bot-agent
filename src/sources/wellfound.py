import json
import re
from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.config import SearchConfig
from src.models import JobListing


class WellfoundSource:
    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        roles = quote(config.keywords.replace(" ", "-").lower())
        url = f"https://wellfound.com/jobs?roles={roles}"
        if config.remote_only:
            url += "&remote=true"
        print(f"  Wellfound: {url[:90]}...")

        jobs: list[JobListing] = []
        kw_parts = [k for k in config.keywords.lower().split() if len(k) > 2]

        try:
            async with AsyncSession(impersonate="chrome124") as client:
                resp = await client.get(url, timeout=30)
                if resp.status_code != 200:
                    print(f"    Wellfound returned {resp.status_code}")
                    return jobs

                text = resp.text
                next_data_match = re.search(
                    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, re.S
                )
                if next_data_match:
                    data = json.loads(next_data_match.group(1))
                    apollo = data.get("props", {}).get("pageProps", {}).get("apolloState", {})
                    for key, node in apollo.items():
                        if key.startswith("JobListing:"):
                            title = node.get("title") or node.get("displayTitle", "")
                            company_data = node.get("company")
                            company = ""
                            if isinstance(company_data, dict):
                                company = company_data.get("name", "")
                            elif isinstance(company_data, str) and company_data.startswith("Company:"):
                                company = apollo.get(company_data, {}).get("name", "")

                            loc = node.get("location", "Remote")
                            href = node.get("jobUrl") or node.get("applyUrl", "")
                            if href and not href.startswith("http"):
                                href = f"https://wellfound.com{href}"

                            desc = node.get("description", "")

                            # Wellfound Apollo cache contains ALL jobs on the page.
                            # Filter by keyword so we don't get Sales Reps.
                            text_combined = f"{title} {desc}".lower()
                            if kw_parts and not any(k in text_combined for k in kw_parts):
                                continue

                            if title and href:
                                jobs.append(
                                    JobListing(
                                        title=title,
                                        company=company,
                                        location=loc,
                                        url=href,
                                        description=desc,
                                        source="wellfound",
                                    )
                                )
                else:
                    # Fallback: link extraction
                    soup = BeautifulSoup(text, "html.parser")
                    seen = set()
                    for link in soup.find_all("a", href=re.compile(r"/jobs/\d+")):
                        href = link.get("href", "")
                        if not href or href in seen:
                            continue
                        seen.add(href)
                        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
                        text_content = link.get_text(separator=" ", strip=True)
                        lines = [ln for ln in text_content.split("\n") if ln.strip()]
                        title = lines[0] if lines else "Unknown"
                        company = lines[1] if len(lines) > 1 else ""

                        text_combined = f"{title}".lower()
                        if kw_parts and not any(k in text_combined for k in kw_parts):
                            continue

                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location="Remote",
                                url=full_url,
                                source="wellfound",
                            )
                        )

                print(f"    {len(jobs)} Wellfound jobs")

        except Exception as e:
            print(f"    Wellfound error: {e}")

        return jobs
