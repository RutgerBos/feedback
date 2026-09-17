"""Deployment contract for the background story worker."""

from pathlib import Path

import yaml


def test_compose_defines_background_worker_service():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())

    worker = compose["services"]["worker"]

    assert worker["command"] == "python -m src.workers.run_worker"
    assert set(worker["depends_on"]) >= {"mongodb", "neo4j", "redis"}
    assert "LLM_PROVIDER=ollama" in worker["environment"]
    assert "./config:/app/config" in worker["volumes"]
