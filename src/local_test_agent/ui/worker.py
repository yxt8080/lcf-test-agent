from __future__ import annotations
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from local_test_agent.services.runtime_logger import RuntimeLogger


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class FunctionWorker(QRunnable):
    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        runtime_logger: RuntimeLogger | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.runtime_logger = runtime_logger
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # pragma: no cover - UI 线程桥接
            if self.runtime_logger is not None:
                self.runtime_logger.exception(
                    "worker.task.failed",
                    "后台任务执行失败。",
                    worker_fn=self._describe_callable(self.fn),
                )
            self.signals.failed.emit(str(exc))
            return
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "worker.task.success",
                "后台任务执行完成。",
                worker_fn=self._describe_callable(self.fn),
            )
        self.signals.finished.emit(result)

    @staticmethod
    def _describe_callable(fn: Callable[..., Any]) -> str:
        return getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))


class BackgroundRunner:
    def __init__(self, runtime_logger: RuntimeLogger | None = None) -> None:
        self.pool = QThreadPool.globalInstance()
        self._active_workers: set[FunctionWorker] = set()
        self.runtime_logger = runtime_logger

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None],
        **kwargs: Any,
    ) -> None:
        if self.runtime_logger is not None:
            self.runtime_logger.info(
                "worker.task.submit",
                "后台任务已提交到线程池。",
                worker_fn=FunctionWorker._describe_callable(fn),
                arg_count=len(args),
                kwarg_keys=sorted(kwargs.keys()),
            )
        worker = FunctionWorker(fn, *args, runtime_logger=self.runtime_logger, **kwargs)
        # PySide 下 QRunnable 若不保留强引用，极端情况下会出现任务线程已启动、
        # 但回调对象提前被回收，导致 UI 一直停留在“处理中”状态。
        # 这里统一托管活动 worker，直到成功或失败回调结束后再释放。
        self._active_workers.add(worker)

        def handle_success(result: Any) -> None:
            self._active_workers.discard(worker)
            on_success(result)

        def handle_error(message: str) -> None:
            self._active_workers.discard(worker)
            on_error(message)

        worker.signals.finished.connect(handle_success)
        worker.signals.failed.connect(handle_error)
        self.pool.start(worker)
