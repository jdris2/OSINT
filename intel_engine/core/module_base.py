"""Core building blocks for the modular intelligence system."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional


class IntelModuleBase(ABC):
    """Base class for all intelligence modules."""

    _TYPE_MAPPING = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": (list, tuple),
    }

    def __init__(
        self,
        module_name: str,
        profile_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the module with optional schemas and a logger.

        Args:
            module_name: Unique identifier for the module.
            profile_schema: JSON-style schema describing the input profile.
            output_schema: JSON-style schema describing the expected output.
            logger: Optional logger; defaults to a module-specific logger.
        """
        self.module_name = module_name
        self.profile_schema = profile_schema or {}
        self.output_schema = output_schema or {}
        self.logger = logger or logging.getLogger(module_name)
        self._current_profile: Optional[Dict[str, Any]] = None
        self._last_result: Any = None

    def execute(self, profile: Dict[str, Any]) -> Any:
        """
        Execute the module against the provided profile.

        Subclasses should override `_execute_impl` to provide module-specific
        behaviour while still benefiting from the validation/logging pipeline.

        Args:
            profile: Profile payload describing the target subject.

        Returns:
            Any data structure produced by the module implementation.
        """
        self._current_profile = profile
        self.validate_input()
        self._last_result = self._execute_impl(profile)
        self.validate_output()
        self.log_result()
        return self._last_result

    @abstractmethod
    def _execute_impl(self, profile: Dict[str, Any]) -> Any:
        """
        Concrete module logic goes here.

        Implementations should perform their analysis and return the resulting
        data structure, which will later be validated and logged by `execute`.
        """

    def validate_input(self) -> None:
        """
        Validate the active profile against the configured schema.

        Raises:
            ValueError: If required fields are missing.
            TypeError: If values do not conform to type hints.
        """
        if self._current_profile is None:
            raise ValueError("No profile has been provided to validate.")

        self._validate_against_schema(
            payload=self._current_profile,
            schema=self.profile_schema,
            payload_name="profile",
        )

    def validate_output(self) -> None:
        """
        Ensure the latest module output matches the configured schema.

        Raises:
            ValueError: If the module output is missing required fields.
            TypeError: If returned values violate type expectations.
        """
        if self._last_result is None:
            raise ValueError(
                "The module has not produced a result to validate yet."
            )

        if not isinstance(self._last_result, dict):
            raise TypeError(
                "Module results must be a dictionary to support schema validation."
            )

        self._validate_against_schema(
            payload=self._last_result,
            schema=self.output_schema,
            payload_name="output",
        )

    def log_result(self) -> None:
        """
        Record the latest validated result with the module tag.

        The default implementation serializes the result to JSON for easy
        downstream processing. Subclasses may override to add more context.
        """
        serialized = json.dumps(
            {
                "module": self.module_name,
                "result": self._last_result,
            },
            default=str,
        )
        self.logger.info("[intel-module:%s] %s", self.module_name, serialized)

    def _validate_against_schema(
        self, payload: Dict[str, Any], schema: Dict[str, Any], payload_name: str
    ) -> None:
        """Run a lightweight validation pass against a JSON-style schema."""
        if not schema:
            return

        required_fields: Iterable[str] = schema.get("required", [])
        for field in required_fields:
            if field not in payload:
                raise ValueError(
                    f"{payload_name} is missing required field '{field}'."
                )

        properties: Dict[str, Dict[str, Any]] = schema.get("properties", {})
        for field_name, definition in properties.items():
            if field_name not in payload:
                continue

            expected_type = definition.get("type")
            if expected_type and expected_type in self._TYPE_MAPPING:
                expected_python_type = self._TYPE_MAPPING[expected_type]
                if not isinstance(payload[field_name], expected_python_type):
                    raise TypeError(
                        f"{payload_name}.{field_name} should be of type "
                        f"'{expected_type}'."
                    )
