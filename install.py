from pip._internal import main as pipmain

_all_ = [
    "toml",
    "aiofiles",
    "colorama",
    "hikari",
    "hikari-lightbulb"
    "mcrcon",
    "mcstatus",
    "pyfiglet",
    "python-valve",
    "youtube_dl",
    "psutil",
    "regex",
    "pytz",
    "aiohttp",
    "python-a2s"
]

windows = []

linux = ["uvloop", "libtmux"]

darwin = ["uvloop"]


def install(packages):
    for package in packages:
        pipmain(['install', package])


if __name__ == '__main__':
    from sys import platform

    install(_all_)
    if platform == 'windows':
        install(windows)
    if platform.startswith('linux'):
        install(linux)
    if platform == 'darwin':
        install(darwin)
