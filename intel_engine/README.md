# Intel Engine Structure

- intel_engine/: Root package tying together the modular OSINT and PI intelligence engine assets.
- core/: Hosts the central orchestrator, shared utilities, and baseline logic for running intelligence workflows.
- modules/: Contains independent intelligence modules that plug into the core orchestration layer.
- schemas/: Stores JSON schema contracts that define the input/output payloads between modules and services.
- ai/: Provides AI-driven planning, decision making, and controller components that guide investigations.
- reports/: Holds generated exports, summaries, and other human-readable reporting artifacts.
- tests/: Includes automated test suites verifying module contracts and engine behaviours.
