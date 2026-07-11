from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from time import sleep

from hardware_sim.snapshots import NetworkInterfaceSnapshot
from hardware_sim.work import NetworkRequirement, WorkInfo


class NetworkInterface:
    def __init__(
        self,
        bandwidth: int,
        latency: float,
        ports: int,
        queue_depth: int,
        name: str = "NIC",
        sink: Callable[[str], None] = print,
    ):
        if bandwidth < 1:
            raise ValueError("bandwidth must be greater than 0")
        if latency < 0:
            raise ValueError("latency must be 0 or greater")
        if ports < 1:
            raise ValueError("ports must be greater than 0")
        if queue_depth < 1:
            raise ValueError("queue_depth must be greater than 0")

        self.name = name
        self._sink = sink
        self.bandwidth = bandwidth
        self.latency = latency
        self.ports = ports
        self.queue_depth = queue_depth
        self._active_transfers = 0
        self._total_received = 0
        self._total_sent = 0
        self._queue_slots = BoundedSemaphore(queue_depth)
        self._lock = Lock()

    def snapshot(self):
        with self._lock:
            return NetworkInterfaceSnapshot(
                name=self.name,
                active_transfers=self._active_transfers,
                queue_depth=self.queue_depth,
                total_received=self._total_received,
                total_sent=self._total_sent,
            )

    def receive(self, work_info: WorkInfo):
        requirement = work_info.requirements.optional(
            "network",
            NetworkRequirement,
        )
        amount = requirement.ingress if requirement is not None else 0
        self._transfer("Received", work_info.id, amount)
        with self._lock:
            self._total_received += amount

    def send(self, work_info: WorkInfo):
        requirement = work_info.requirements.optional(
            "network",
            NetworkRequirement,
        )
        amount = requirement.egress if requirement is not None else 0
        self._transfer("Sent", work_info.id, amount)
        with self._lock:
            self._total_sent += amount

    def _transfer(self, action: str, work_id: int, amount: int):
        if amount <= 0:
            return

        self._queue_slots.acquire()
        try:
            with self._lock:
                self._active_transfers += 1

            duration = self.latency + amount / self.bandwidth
            self._sink(f"[{self.name}] {action}: id={work_id}, amount={amount}")
            sleep(duration)
        finally:
            with self._lock:
                self._active_transfers -= 1
            self._queue_slots.release()
