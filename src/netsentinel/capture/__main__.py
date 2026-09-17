"""Saída JSON Lines para inspeção antes da integração com o backend."""
import argparse
import json
import signal
import sys
from threading import Event
from netsentinel.capture.config import CaptureConfig
from netsentinel.capture.service import CaptureService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--window-seconds", type=float, required=True)
    parser.add_argument("--max-observations", type=int, required=True)
    parser.add_argument("--isolated-lab", action="store_true")
    args = parser.parse_args()
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        config = CaptureConfig(args.interface, args.window_seconds,
                               args.max_observations, args.isolated_lab)
        CaptureService(config, lambda data: print(json.dumps(data), flush=True)).run(stop)
    except (ValueError, OSError) as exc:
        print(f"Captura interrompida: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
