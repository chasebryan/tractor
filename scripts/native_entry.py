import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--smoke-test" in sys.argv:
        from tractor.packaging_smoke import run

        raise SystemExit(run())
    from tractor.app import main

    raise SystemExit(main())
