import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from misc.recruit_deadline import (
    get_recruit_deadline, parse_deadline, require_recruitment_open,
    set_recruit_deadline,
)
from models.site_setting import SiteSetting
from models.recruit import Recruitment
from misc.recruit_options import undergraduate_major, validate_enrollment_grade
from routes.recruit import RecruitApplication


class DeadlineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.url = "sqlite:///" + str(Path(self.temp.name) / "settings.sqlite")
        self.engine = create_engine(self.url)
        SiteSetting.__table__.create(self.engine)
        Recruitment.__table__.create(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_timezone_and_validation(self):
        expected = "2026-09-30T23:59:00+08:00"
        for value in ["2026-09-30", "2026-09-30T23:59", "2026-09-30T15:59:00Z"]:
            self.assertEqual(parse_deadline(value).isoformat(), expected)
        for value in ["2026-02-30", "2026-09-30T25:00", "not-a-date"]:
            with self.assertRaises(ValueError):
                parse_deadline(value)

    def test_migration_preserves_database_over_legacy_cache(self):
        with Session(self.engine) as db:
            with patch("misc.recruit_deadline.get_config", return_value=SimpleNamespace(RECRUIT_DEADLINE="2026-05-10")):
                self.assertEqual(get_recruit_deadline(db).date().isoformat(), "2026-05-10")
                set_recruit_deadline(db, "2026-09-30T23:59+08:00")
                self.assertEqual(get_recruit_deadline(db).isoformat(), "2026-09-30T23:59:00+08:00")
        with Session(self.engine) as db:
            self.assertEqual(get_recruit_deadline(db).date().isoformat(), "2026-09-30")

    def test_exact_deadline_boundary(self):
        deadline = parse_deadline("2026-09-30T23:59+08:00")
        before = parse_deadline("2026-09-30T23:58:59+08:00")
        with patch("misc.recruit_deadline.get_recruit_deadline", return_value=deadline):
            with patch("misc.recruit_deadline.datetime") as clock:
                clock.now.return_value = before
                require_recruitment_open(None)
                clock.now.return_value = deadline
                with self.assertRaises(HTTPException) as error:
                    require_recruitment_open(None)
                self.assertEqual(error.exception.status_code, 403)

    def test_new_cohort_and_manual_major_validation(self):
        with patch("misc.recruit_options.current_enrollment_year", return_value=2026):
            self.assertEqual(validate_enrollment_grade(26), 26)
            with self.assertRaises(ValueError):
                validate_enrollment_grade(27)
        with patch("misc.recruit_options.CATALOG_DIR", Path(self.temp.name)):
            details = undergraduate_major(SimpleNamespace(
                grade=26, major_name="  网络空间安全 ", college_name="计算机科学与技术学院",
            ))
            self.assertEqual(details["major_name"], "网络空间安全")
            self.assertIsNone(details["major_id"])
            self.assertIsNone(details["college_id"])
            with self.assertRaises(HTTPException):
                undergraduate_major(SimpleNamespace(grade=26, major_name="专业", college_name=""))

    def test_four_uvicorn_workers_see_updates_without_restart(self):
        with Session(self.engine) as db:
            set_recruit_deadline(db, "2000-01-01T23:59+08:00")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, CSA_DEADLINE_TEST_DB_URL=self.url)
        log = tempfile.TemporaryFile()
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "tests.deadline_app:app",
             "--host", "127.0.0.1", "--port", str(port), "--workers", "4",
             "--log-level", "error"],
            cwd=Path(__file__).resolve().parents[1], env=env,
            stdout=log, stderr=log,
        )
        base = f"http://127.0.0.1:{port}"

        def request(path="/deadline", body=None, authorized=True):
            headers = {"Connection": "close"}
            if authorized:
                headers["X-Test-Key"] = "isolated-deadline-test"
            data = None if body is None else json.dumps(body).encode()
            if data is not None:
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(base + path, data=data, headers=headers)
            try:
                response = urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, dict(response.headers), json.load(response)

        def sample(expected, is_open):
            workers = set()
            for _ in range(160):
                status, headers, payload = request()
                self.assertEqual(status, 200)
                self.assertEqual(payload["deadline"], expected)
                self.assertEqual(payload["is_open"], is_open)
                workers.add(headers["x-test-worker"])
                if len(workers) == 4:
                    return workers
            self.fail(f"Only reached {len(workers)} workers")

        try:
            for _ in range(120):
                if process.poll() is not None:
                    log.seek(0)
                    self.fail(log.read().decode())
                try:
                    request()
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.1)
            old_workers = sample("2000-01-01T23:59:00+08:00", False)
            self.assertEqual(request(body={"deadline": "2099-09-30T23:59+08:00"}, authorized=False)[0], 401)
            self.assertEqual(request(body={"deadline": "2099-09-30T23:59+08:00"})[0], 200)
            new_workers = sample("2099-09-30T23:59:00+08:00", True)
            self.assertEqual(old_workers, new_workers)
            _, _, options = request("/options")
            self.assertIn(26, options["grades"])
            payload = {
                "name": "Test", "render": True, "uid": "1234567890",
                "major_name": "网络空间安全", "college_name": "计算机科学与技术学院",
                "degree": 0, "grade": 26, "phone": "13800000000",
                "office_department_willing": 1, "competition_department_willing": 2,
                "activity_department_willing": 3, "research_department_willing": 4,
                "if_agree_to_be_reassigned": True, "if_be_member": True,
                "introduction": "", "skill": "",
            }
            self.assertEqual(request("/recruit", payload)[0], 200)
            with Session(self.engine) as db:
                recruit = db.get(Recruitment, "1234567890")
                self.assertEqual(recruit.grade, 26)
                self.assertEqual(recruit.college_name, "计算机科学与技术学院")
                self.assertIsNone(recruit.major_id)
                self.assertIsNone(recruit.college_id)
            self.assertEqual(request(body={"deadline": "2026-02-30"})[0], 400)
            self.assertEqual(request(body={"deadline": "2000-01-01"})[0], 200)
            self.assertEqual(sample("2000-01-01T23:59:00+08:00", False), old_workers)
            payload = {
                "name": "Test", "render": True, "uid": "1234567890",
                "major_name": "Test", "degree": 1, "grade": 25,
                "phone": "13800000000", "office_department_willing": 1,
                "competition_department_willing": 2, "activity_department_willing": 3,
                "research_department_willing": 4, "if_agree_to_be_reassigned": True,
                "if_be_member": True, "introduction": "", "skill": "",
            }
            status, _, body = request("/recruit", payload)
            self.assertEqual(status, 403)
            self.assertIn("截止", body["detail"])
            print(f"Verified unchanged worker PIDs: {sorted(old_workers)}", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()


if __name__ == "__main__":
    unittest.main()
