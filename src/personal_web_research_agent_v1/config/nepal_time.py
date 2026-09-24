from datetime import datetime
import pytz

_NEPAL_TZ = pytz.timezone("Asia/Kathmandu")


def nepal_date_now() -> datetime:
    """Return the current Nepal time as a timezone-aware datetime."""
    return datetime.now(_NEPAL_TZ)


def nepal_date_today() -> str:
    """Return today's date in Nepal as a YYYY-MM-DD string."""
    return nepal_date_now().strftime("%Y-%m-%d")