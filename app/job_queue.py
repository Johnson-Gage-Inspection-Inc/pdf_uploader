"""
job_queue.py -- Centralized job queue for parallel PDF processing.

Decouples file detection (watcher) from file processing (workers).
Each detected PDF is submitted as a job to a ThreadPoolExecutor-backed
queue with a configurable ``max_workers`` setting.

Singleton access mirrors the event_bus pattern:
    init_queue(max_workers)   -- call once at startup
    get_queue()               -- returns the singleton (or None)
    shutdown_queue()          -- drain and stop all workers
"""

from __future__ import annotations

import logging
import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import app.color_print as cp
from app.config_manager import WatchedFolder

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Metadata for a single PDF processing job."""

    filepath: str
    folder: WatchedFolder
    submitted_at: datetime = field(default_factory=datetime.now)
    future: Optional[Future] = field(default=None, repr=False)


class JobQueue:
    """Thread-pool-backed job queue for parallel PDF processing.

    Each submitted file runs ``upload.process_file()`` in a worker thread.
    The pool size is capped at ``max_workers``.
    """

    def __init__(self, max_workers: int = 3):
        self._max_workers = max(1, max_workers)
        self._pool = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="pdf-worker",
        )
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}  # filepath -> Job
        self._shutdown = False

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def pending_count(self) -> int:
        """Number of jobs waiting to start (submitted but not yet running)."""
        with self._lock:
            return sum(
                1
                for j in self._jobs.values()
                if j.future is not None
                and not j.future.running()
                and not j.future.done()
            )

    @property
    def active_count(self) -> int:
        """Number of jobs currently executing in worker threads."""
        with self._lock:
            return sum(
                1
                for j in self._jobs.values()
                if j.future is not None and j.future.running()
            )

    @property
    def total_queued(self) -> int:
        """Total jobs that haven't finished yet (pending + active)."""
        with self._lock:
            return sum(
                1
                for j in self._jobs.values()
                if j.future is not None and not j.future.done()
            )

    def submit(self, filepath: str, folder: WatchedFolder) -> Optional[Job]:
        """Submit a file for processing.

        Returns the Job if submitted, or None if the queue is shut down
        or the file is already queued.
        """
        with self._lock:
            if self._shutdown:
                cp.yellow(f"Queue is shut down, ignoring: {filepath}")
                return None

            existing = self._jobs.get(filepath)
            if existing is not None:
                # Treat any in-progress or pending job (including placeholders)
                # as already queued to avoid duplicate submissions.
                if existing.future is None or not existing.future.done():
                    cp.yellow(f"Already queued: {filepath}")
                    return None

            # Register the job under the lock first to close the race
            # with _run_job's cleanup.
            job = Job(filepath=filepath, folder=folder)
            self._jobs[filepath] = job

        # Submit work to the pool outside the lock to avoid blocking other
        # operations on the queue while the executor schedules the task.
        # Clean up the placeholder if the pool rejects the task (e.g., already shut down).
        try:
            future = self._pool.submit(self._run_job, job)
        except RuntimeError as exc:
            # This commonly happens if the underlying ThreadPoolExecutor is
            # shutting down between our _shutdown check and submit().
            with self._lock:
                self._jobs.pop(filepath, None)
            logger.warning(
                "JobQueue executor rejected task for %s (likely shutting down): %s",
                filepath,
                exc,
            )
            return None
        except Exception:
            # For unexpected errors, still clean up the placeholder and re-raise.
            with self._lock:
                self._jobs.pop(filepath, None)
            raise
        job.future = future

        cp.blue(f"Queued for processing: {filepath}")
        return job

    def _run_job(self, job: Job) -> bool:
        """Execute a single processing job in a worker thread.

        Calls ``upload.process_file()`` and handles exceptions so that
        one failing job never crashes the pool.
        """
        from upload import process_file

        try:
            result = process_file(job.filepath, job.folder)
            return bool(result)
        except Exception as exc:
            cp.red(f"Job failed for {job.filepath}: {exc}")
            logger.error("Job failed: %s\n%s", job.filepath, traceback.format_exc())
            # Emit a failure event so the dashboard reflects the error
            try:
                import os
                from app.event_bus import ProcessingEvent

                ProcessingEvent(
                    filepath=job.filepath,
                    filename=os.path.basename(job.filepath),
                    timestamp=datetime.now(),
                    success=False,
                    error_message=f"Unexpected error: {exc}",
                    folder_label=job.folder.input_dir,
                ).emit()
            except Exception:
                pass
            return False
        finally:
            with self._lock:
                self._jobs.pop(job.filepath, None)

    def shutdown(self, wait: bool = True, timeout: float = 60.0) -> None:
        """Gracefully shut down the worker pool.

        Args:
            wait: If True, block until in-flight jobs complete, bounded by *timeout* seconds.
            timeout: Maximum seconds to wait for in-flight jobs when wait=True.
        """
        self._shutdown = True
        cp.white(f"Shutting down job queue (wait={wait}, timeout={timeout}s)...")
        if wait:
            from concurrent.futures import wait as wait_futures

            with self._lock:
                pending = [
                    j.future
                    for j in self._jobs.values()
                    if j.future is not None and not j.future.done()
                ]
            wait_futures(pending, timeout=timeout)
        self._pool.shutdown(wait=wait, cancel_futures=True)
        cp.white("Job queue stopped.")


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_queue: Optional[JobQueue] = None


def get_queue() -> Optional[JobQueue]:
    """Return the job queue singleton, or None if not initialized."""
    return _queue


def init_queue(max_workers: int = 3) -> JobQueue:
    """Initialize the job queue singleton. Call once at startup."""
    global _queue
    _queue = JobQueue(max_workers=max_workers)
    cp.white(f"Job queue initialized with {max_workers} workers.")
    return _queue


def shutdown_queue(wait: bool = True, timeout: float = 60.0) -> None:
    """Shut down the global job queue if it exists."""
    global _queue
    if _queue is not None:
        _queue.shutdown(wait=wait, timeout=timeout)
        _queue = None
