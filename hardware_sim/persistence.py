import json
from pathlib import Path
from threading import Event, Thread


class AutosaveWorker:
    def __init__(
        self,
        source: object,
        save_path: str | Path,
        interval: float = 0.25,
    ):
        if interval <= 0:
            raise ValueError("interval must be greater than 0")

        self.source = source
        self.save_path = Path(save_path)
        self.interval = interval
        self._last_saved_version = source.state_version
        self._stop_event = Event()
        self._thread = Thread(
            target=self._run,
            name="autosave-worker",
            daemon=True,
        )

    def start(self):
        self._thread.start()

    def stop(self):
        self.flush()
        self._stop_event.set()
        self._thread.join()

    def flush(self):
        version, data = self.source.save_snapshot()
        if version != self._last_saved_version:
            self._write(data)
            self._last_saved_version = version

    def _run(self):
        while not self._stop_event.wait(self.interval):
            self.flush()

    def _write(self, data: dict[str, object]):
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.save_path.with_suffix(f"{self.save_path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        temporary_path.replace(self.save_path)
