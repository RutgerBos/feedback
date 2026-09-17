"""Story submission remains successful when the queue is temporarily unavailable."""

import pytest

from src.services.story_submission import (
    SignificationRequest,
    StorySubmissionRequest,
    StorySubmissionResult,
    TriadResponseRequest,
)


class RecordingSubmissionService:
    def __init__(self) -> None:
        self.requests: list[StorySubmissionRequest] = []

    def submit_story(self, request: StorySubmissionRequest) -> StorySubmissionResult:
        self.requests.append(request)
        return StorySubmissionResult(story_id="story-saved")


class FailingQueue:
    def enqueue(self, story_id: str) -> None:
        raise ConnectionError("redis unavailable")


@pytest.mark.asyncio
async def test_api_returns_saved_result_when_enqueue_fails():
    from src.api.stories import submit_story

    request = StorySubmissionRequest(
        story_text="A sufficiently long account of a difficult deployment experience.",
        signification=SignificationRequest(
            responses=[
                TriadResponseRequest(
                    signifier_id="workflow_nature",
                    coordinates={"x": 0.5, "y": 0.5},
                )
            ]
        ),
    )

    result = await submit_story(
        request=request,
        service=RecordingSubmissionService(),  # type: ignore[arg-type]
        queue=FailingQueue(),  # type: ignore[arg-type]
    )

    assert result.story_id == "story-saved"
