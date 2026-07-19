from abc import ABC, abstractmethod


class Integration(ABC):
    """Common interface for every task integration (weather, calendar, spotify, ...).

    Swapping a stub for a real API later means editing one subclass --
    the permission gate and registry never change.
    """

    @abstractmethod
    def execute(self, params: dict) -> dict:
        ...
