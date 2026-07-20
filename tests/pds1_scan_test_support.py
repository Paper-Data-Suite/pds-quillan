"""Legacy PDS1 samples used only by later-ticket scan-intake tests."""


def build_response_payload(
    class_id: str,
    assignment_id: str,
    student_id: str,
    page: int,
) -> str:
    """Return the historical PDS1 fixture text without a generation API."""
    return (
        f"PDS1|module=quillan|class={class_id}|aid={assignment_id}|"
        f"sid={student_id}|page={page}|doc=response"
    )
