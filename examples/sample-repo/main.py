"""Sample project file for SafeClaw demo."""

# TODO: Implement proper authentication
# FIXME: This function is too slow for large datasets
# HACK: Temporary workaround until v2 API is ready

API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"  # noqa: S105 — intentional for demo


def process_data(items: list) -> dict:
    """Process incoming data items.

    TODO: Add input validation
    FIXME: Handle empty list case
    """
    results = {}
    for item in items:
        results[item["id"]] = item["value"] * 2
    return results


def connect_to_service():
    """Connect to external service.

    HACK: Using hardcoded URL until config system is built
    """
    url = "https://api.example.com/v1"
    token = "github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"  # noqa: S105
    return {"url": url, "token": token}
