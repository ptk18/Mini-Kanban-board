from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Attach the UTC offset to a stored naive-UTC timestamp.

    Same convention as ``UserOut``: the JSON carries an explicit "Z" so
    browsers do not read the value as local time.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
