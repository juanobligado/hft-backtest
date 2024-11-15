from datetime import datetime, timedelta

def nanosecond_timestamp_to_date(nanosecond_timestamp: int) -> datetime:
    # Convert nanoseconds to seconds
    seconds = nanosecond_timestamp // 1_000_000_000
    nanoseconds = nanosecond_timestamp % 1_000_000_000

    # Create a datetime object from the seconds
    dt = datetime.fromtimestamp(seconds)

    # Add the remaining nanoseconds as a timedelta
    dt = dt + timedelta(microseconds=nanoseconds / 1_000)

    return dt