from datetime import datetime
import platform
import sys
import resource


def string_to_datetime(string_time: str) -> datetime:
    return datetime.strptime(string_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def _memory_limit(percentage: float):
    if platform.system() != "Linux":
        print(
            """
            Memory limitation currently only works on Linux systems!
            Be careful, your comuter can freeze!
            """
        )
        return
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(
        resource.RLIMIT_AS, (_get_memory() * 1024 * percentage, hard)
    )


def _get_memory():
    with open("/proc/meminfo", "r", encoding="utf8") as mem:
        free_memory = 0
        for i in mem:
            sline = i.split()
            if str(sline[0]) in ("MemFree:", "Buffers:", "Cached:"):
                free_memory += int(sline[1])
    return free_memory


def memory(percentage=0.8):
    def decorator(function):
        def wrapper(*args, **kwargs):
            _memory_limit(percentage)
            try:
                function(*args, **kwargs)
            except MemoryError:
                mem = _get_memory() / 1024 / 1024
                print(f"Remain: {mem:.2f} GB")
                sys.stderr.write("\n\nERROR: Memory Exception\n")
                sys.exit(1)

        return wrapper

    return decorator
