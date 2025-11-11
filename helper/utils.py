import math
import time
from pyrogram.types import Message

async def progress_bar(current, total, message: Message, start, process_name="Processing"):
    """Show real-time progress bar for uploads/downloads."""
    now = time.time()
    diff = now - start

    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff != 0 else 0
        elapsed_time = round(diff)
        eta = round((total - current) / speed) if speed != 0 else 0
        elapsed_time_str = time_formatter(elapsed_time)
        eta_str = time_formatter(eta)
        progress = "[{0}{1}]".format(
            ''.join(["█" for _ in range(math.floor(percentage / 10))]),
            ''.join(["░" for _ in range(10 - math.floor(percentage / 10))])
        )

        tmp = f"**{process_name}**\n{progress} `{percentage:.1f}%`\n" \
              f"⏱️ Elapsed: `{elapsed_time_str}` | ⏳ ETA: `{eta_str}`\n" \
              f"⚡ Speed: `{humanbytes(speed)}/s`"

        try:
            await message.edit_text(tmp)
        except Exception:
            pass


def time_formatter(seconds: int) -> str:
    """Convert seconds into human-readable format."""
    result = ""
    intervals = (
        ('week', 604800),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1),
    )
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            result += f"{value} {name}{'s' if value > 1 else ''} "
    return result.strip() or "0s"


def humanbytes(size):
    """Convert bytes to human-readable size (e.g., MB, GB)."""
    if not size:
        return "0 B"
    power = 2**10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels[n]}"
