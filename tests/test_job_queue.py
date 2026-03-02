"""Tests for app.job_queue -- parallel PDF processing queue."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app.config_manager import WatchedFolder
from app.job_queue import JobQueue, init_queue, get_queue, shutdown_queue


class TestJobQueueInit(unittest.TestCase):
    """Test queue initialization and singleton management."""

    def tearDown(self):
        shutdown_queue(wait=False)

    def test_get_queue_returns_none_before_init(self):
        import app.job_queue as jq

        jq._queue = None
        self.assertIsNone(get_queue())

    def test_init_queue_returns_instance(self):
        q = init_queue(max_workers=2)
        self.assertIsInstance(q, JobQueue)
        self.assertEqual(q.max_workers, 2)

    def test_get_queue_after_init(self):
        init_queue(max_workers=2)
        self.assertIsNotNone(get_queue())

    def test_shutdown_clears_singleton(self):
        init_queue(max_workers=1)
        shutdown_queue(wait=True)
        self.assertIsNone(get_queue())

    def test_max_workers_minimum_is_one(self):
        q = JobQueue(max_workers=0)
        self.assertEqual(q.max_workers, 1)
        q.shutdown(wait=False)

        q2 = JobQueue(max_workers=-5)
        self.assertEqual(q2.max_workers, 1)
        q2.shutdown(wait=False)


class TestJobQueueSubmit(unittest.TestCase):
    """Test job submission and execution."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.folder = WatchedFolder(
            input_dir=self.tmpdir,
            output_dir=os.path.join(self.tmpdir, "archive"),
            reject_dir=os.path.join(self.tmpdir, "reject"),
            qualer_document_type="General",
            validate_po=False,
        )

    def tearDown(self):
        shutdown_queue(wait=True, timeout=5.0)
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("app.job_queue.JobQueue._run_job")
    def test_submit_returns_job(self, mock_run):
        mock_run.return_value = True
        q = init_queue(max_workers=2)
        filepath = os.path.join(self.tmpdir, "test.pdf")
        with open(filepath, "w") as f:
            f.write("dummy")
        if job := q.submit(filepath, self.folder):
            self.assertIsNotNone(job)
            self.assertEqual(job.filepath, filepath)
            self.assertEqual(job.folder, self.folder)
        else:
            self.fail("submit() returned None unexpectedly")

    @patch("app.job_queue.JobQueue._run_job")
    def test_submit_duplicate_returns_none(self, mock_run):
        # Make _run_job block so the first job stays in-flight
        barrier = threading.Event()
        mock_run.side_effect = lambda j: barrier.wait(timeout=5)

        q = init_queue(max_workers=2)
        filepath = os.path.join(self.tmpdir, "test.pdf")
        with open(filepath, "w") as f:
            f.write("dummy")

        job1 = q.submit(filepath, self.folder)
        self.assertIsNotNone(job1)

        job2 = q.submit(filepath, self.folder)
        self.assertIsNone(job2)  # Duplicate rejected

        barrier.set()  # Unblock

    @patch("app.job_queue.JobQueue._run_job")
    def test_submit_after_shutdown_returns_none(self, mock_run):
        q = init_queue(max_workers=1)
        q.shutdown(wait=False)

        filepath = os.path.join(self.tmpdir, "test.pdf")
        with open(filepath, "w") as f:
            f.write("dummy")
        job = q.submit(filepath, self.folder)
        self.assertIsNone(job)


class TestJobQueueConcurrency(unittest.TestCase):
    """Test that jobs actually run in parallel."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.folder = WatchedFolder(
            input_dir=self.tmpdir,
            output_dir=os.path.join(self.tmpdir, "archive"),
            reject_dir=os.path.join(self.tmpdir, "reject"),
            qualer_document_type="General",
            validate_po=False,
        )

    def tearDown(self):
        shutdown_queue(wait=True, timeout=10.0)
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("upload.process_file")
    def test_parallel_execution(self, mock_process):
        """Multiple jobs should execute concurrently up to max_workers."""
        barrier = threading.Barrier(2, timeout=5)
        done_events = [threading.Event() for _ in range(2)]

        call_count = 0
        call_lock = threading.Lock()

        def slow_process(filepath, folder):
            nonlocal call_count
            idx = int(os.path.basename(filepath).split("_")[1].split(".")[0])
            barrier.wait()  # Both threads must reach here
            with call_lock:
                call_count += 1
            done_events[idx].set()
            return True

        mock_process.side_effect = slow_process

        q = init_queue(max_workers=2)

        files = []
        for i in range(2):
            fp = os.path.join(self.tmpdir, f"test_{i}.pdf")
            with open(fp, "w") as f:
                f.write("dummy")
            files.append(fp)

        for fp in files:
            q.submit(fp, self.folder)

        # Wait deterministically for both jobs to finish
        for ev in done_events:
            self.assertTrue(ev.wait(timeout=10), "Job did not complete in time")
        self.assertEqual(call_count, 2)

    @patch("upload.process_file")
    def test_max_workers_respected(self, mock_process):
        """No more than max_workers jobs should run simultaneously."""
        max_concurrent = 0
        current = 0
        lock = threading.Lock()
        all_done = threading.Event()
        completed = 0
        total_jobs = 5

        def track_concurrency(filepath, folder):
            nonlocal max_concurrent, current, completed
            with lock:
                current += 1
                max_concurrent = max(max_concurrent, current)
            time.sleep(0.2)  # Simulate work
            with lock:
                current -= 1
                completed += 1
                if completed >= total_jobs:
                    all_done.set()
            return True

        mock_process.side_effect = track_concurrency

        q = init_queue(max_workers=2)

        files = []
        for i in range(total_jobs):
            fp = os.path.join(self.tmpdir, f"test_{i}.pdf")
            with open(fp, "w") as f:
                f.write("dummy")
            files.append(fp)

        for fp in files:
            q.submit(fp, self.folder)

        # Wait deterministically for all jobs to complete
        self.assertTrue(all_done.wait(timeout=30), "Not all jobs completed in time")
        self.assertLessEqual(max_concurrent, 2)
        self.assertEqual(mock_process.call_count, total_jobs)


class TestJobQueueErrorHandling(unittest.TestCase):
    """Test that errors in one job don't crash the pool."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.folder = WatchedFolder(
            input_dir=self.tmpdir,
            output_dir=os.path.join(self.tmpdir, "archive"),
            reject_dir=os.path.join(self.tmpdir, "reject"),
            qualer_document_type="General",
            validate_po=False,
        )

    def tearDown(self):
        shutdown_queue(wait=True, timeout=5.0)
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("upload.process_file")
    def test_exception_does_not_crash_pool(self, mock_process):
        """A job that raises should not prevent subsequent jobs from running."""
        results = []
        lock = threading.Lock()
        ok_done = threading.Event()

        def alternating(filepath, folder):
            name = os.path.basename(filepath)
            if "fail" in name:
                raise RuntimeError("Simulated failure")
            with lock:
                results.append(name)
            ok_done.set()
            return True

        mock_process.side_effect = alternating

        q = init_queue(max_workers=2)

        # Create a failing file and a succeeding file
        fail_fp = os.path.join(self.tmpdir, "fail.pdf")
        ok_fp = os.path.join(self.tmpdir, "ok.pdf")
        for fp in (fail_fp, ok_fp):
            with open(fp, "w") as f:
                f.write("dummy")

        q.submit(fail_fp, self.folder)
        q.submit(ok_fp, self.folder)

        self.assertTrue(ok_done.wait(timeout=10), "OK job did not complete")
        self.assertIn("ok.pdf", results)

    @patch("upload.process_file")
    def test_failed_job_removed_from_tracking(self, mock_process):
        """After a job fails, the filepath should be removed from _jobs."""

        def fail_then_signal(filepath, folder):
            raise RuntimeError("boom")

        mock_process.side_effect = fail_then_signal

        q = init_queue(max_workers=1)
        fp = os.path.join(self.tmpdir, "test.pdf")
        with open(fp, "w") as f:
            f.write("dummy")

        job = q.submit(fp, self.folder)
        self.assertIsNotNone(job)
        # Wait for the future to complete (deterministic — no sleep)
        job.future.result(timeout=5)  # type: ignore[union-attr]

        # The filepath should be cleaned up
        self.assertNotIn(fp, q._jobs)


class TestJobQueueCounters(unittest.TestCase):
    """Test pending_count, active_count, total_queued properties."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.folder = WatchedFolder(
            input_dir=self.tmpdir,
            output_dir=os.path.join(self.tmpdir, "archive"),
            reject_dir=os.path.join(self.tmpdir, "reject"),
            qualer_document_type="General",
            validate_po=False,
        )

    def tearDown(self):
        shutdown_queue(wait=True, timeout=5.0)
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_counters_start_at_zero(self):
        q = init_queue(max_workers=2)
        self.assertEqual(q.pending_count, 0)
        self.assertEqual(q.active_count, 0)
        self.assertEqual(q.total_queued, 0)

    @patch("upload.process_file")
    def test_total_queued_during_processing(self, mock_process):
        barrier = threading.Event()

        def block(filepath, folder):
            barrier.wait(timeout=10)
            return True

        mock_process.side_effect = block

        q = init_queue(max_workers=1)

        fp = os.path.join(self.tmpdir, "test.pdf")
        with open(fp, "w") as f:
            f.write("dummy")

        q.submit(fp, self.folder)
        time.sleep(0.5)

        self.assertGreaterEqual(q.total_queued, 1)

        barrier.set()


class TestConfigMaxWorkers(unittest.TestCase):
    """Test that max_workers is properly loaded from config."""

    def test_appconfig_default_max_workers(self):
        from app.config_manager import AppConfig

        cfg = AppConfig()
        self.assertEqual(cfg.max_workers, 3)

    def test_config_facade_exposes_max_workers(self):
        import app.config as config

        self.assertIsInstance(config.MAX_WORKERS, int)
        self.assertGreaterEqual(config.MAX_WORKERS, 1)


if __name__ == "__main__":
    unittest.main()
