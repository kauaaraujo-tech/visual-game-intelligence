"""Official VGI entry point, sharing the existing diagnostic implementation."""
from urd.__main__ import main as _legacy_main


def main(argv=None):
    return _legacy_main(argv, prog='python -m vgi')


if __name__ == '__main__':
    raise SystemExit(main())
