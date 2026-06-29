import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.models.application import Application
from src.models.job import Job


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def initialize(self):
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                employment_type TEXT,
                salary TEXT,
                description TEXT NOT NULL,
                skills TEXT,
                apply_url TEXT,
                posted_date TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                answers TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                submitted_at TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );
        """)
        conn.commit()

    @contextmanager
    def get_connection(self):
        conn = self.connect()
        try:
            yield conn
        finally:
            pass

    def save_job(self, job: Job) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs
                    (id, source, company, title, location, employment_type,
                     salary, description, skills, apply_url, posted_date, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.source,
                    job.company,
                    job.title,
                    job.location,
                    job.employment_type,
                    job.salary,
                    job.description,
                    json.dumps(job.skills) if job.skills else None,
                    job.apply_url,
                    job.posted_date.isoformat() if job.posted_date else None,
                    json.dumps(job.metadata) if job.metadata else None,
                ),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Job | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self) -> list[Job]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [self._row_to_job(r) for r in rows]

    def save_application(self, app: Application) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO applications
                    (id, job_id, status, answers, created_at, updated_at, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app.id,
                    app.job_id,
                    app.status,
                    json.dumps(app.answers) if app.answers else None,
                    app.created_at.isoformat(),
                    app.updated_at.isoformat(),
                    app.submitted_at.isoformat() if app.submitted_at else None,
                ),
            )
            conn.commit()

    def get_application(self, app_id: str) -> Application | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_application(row)

    def list_applications(self) -> list[Application]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
        return [self._row_to_application(r) for r in rows]

    def update_application_status(self, app_id: str, status: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), app_id),
            )
            conn.commit()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        posted = row["posted_date"]
        return Job(
            id=row["id"],
            source=row["source"],
            company=row["company"],
            title=row["title"],
            location=row["location"],
            employment_type=row["employment_type"],
            salary=row["salary"],
            description=row["description"],
            skills=json.loads(row["skills"]) if row["skills"] else [],
            apply_url=row["apply_url"],
            posted_date=datetime.fromisoformat(posted) if posted else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    @staticmethod
    def _row_to_application(row: sqlite3.Row) -> Application:
        answers_raw = row["answers"]
        submitted_raw = row["submitted_at"]
        return Application(
            id=row["id"],
            job_id=row["job_id"],
            status=row["status"],
            answers=json.loads(answers_raw) if answers_raw else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            submitted_at=datetime.fromisoformat(submitted_raw) if submitted_raw else None,
        )
