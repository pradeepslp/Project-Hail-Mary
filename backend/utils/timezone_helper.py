from datetime import datetime, timezone, timedelta

def ist_now() -> datetime:
    """Return the current time in India Standard Time (UTC+5:30) as naive datetime."""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).replace(tzinfo=None)
