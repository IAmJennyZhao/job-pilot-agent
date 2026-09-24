from datetime import datetime, timezone
from test_api import create_job


def test_job_api_timestamps_are_unambiguous_utc(client):
    job = create_job(client)
    for value in [job['created_at'], job['updated_at'], job['status_events'][0]['changed_at']]:
        parsed = datetime.fromisoformat(value)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
