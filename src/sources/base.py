from abc import ABC, abstractmethod

from src.models.job import Job


class Source(ABC):
    @abstractmethod
    async def discover(self) -> list[Job]:
        ...
