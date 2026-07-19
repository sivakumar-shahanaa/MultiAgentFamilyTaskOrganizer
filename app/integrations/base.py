from abc import ABC, abstractmethod

from sqlmodel import Session


class Integration(ABC):
    """Common interface for every task integration (weather, calendar, spotify, ...).

    execute() is async and receives a DB session because integrations that
    talk to real external APIs (Spotify) need to look up stored credentials.
    Integrations that don't need the DB can just ignore the `session` arg.
    """

    @abstractmethod
    async def execute(self, params: dict, session: Session) -> dict:
        ...
