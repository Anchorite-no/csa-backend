import json
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from misc.recruit_contacts import get_minister_wechat
from models import Base
from models.member import Member
from models.recruit import Recruitment
from models.user import User
from routes.recruit import FinalAcceptRequest, final_accept


class AdmissionContactsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "recruitment.json"
        self.contacts = {
            "office": "test_office", "competition": "test_competition",
            "research": "test_research", "activity": "test_activity",
        }
        self.write_config({"minister_wechat": self.contacts})
        self.patch("misc.recruit_contacts.CONTACTS_FILE", self.path)
        self.send = self.patch("routes.recruit.send_dingtalk_message_to_user", return_value=True)
        self.patch("routes.recruit.hash_passwd", return_value="test-password-hash")
        self.patch("requests.sessions.Session.request", side_effect=AssertionError("Network is disabled in this test"))

    def patch(self, *args, **kwargs):
        patcher = patch(*args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def write_config(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    @contextmanager
    def database(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                candidate = Recruitment(
                    uid="1260000001", name="Test", grade=26,
                    first_round_passed=True, second_round_passed=True,
                )
                db.add(candidate)
                db.commit()
                yield db, candidate
        finally:
            engine.dispose()

    def test_each_department_uses_its_configured_contact(self):
        for department, expected in self.contacts.items():
            with self.subTest(department=department), self.database() as (db, candidate):
                self.send.reset_mock()
                result = final_accept(FinalAcceptRequest(uid=candidate.uid, department=department), db, True)
                self.assertTrue(result["success"])
                self.assertTrue(db.get(Recruitment, candidate.uid).is_admitted)
                self.assertEqual(db.get(Member, candidate.uid).department, department)
                self.assertIsNotNone(db.get(User, candidate.uid))
                self.send.assert_called_once()
                description = self.send.call_args.kwargs["description"]
                self.assertIn(f"请添加部门部长微信: {expected}", description)
                for other in set(self.contacts.values()) - {expected}:
                    self.assertNotIn(other, description)

    def test_config_updates_are_visible_without_restart(self):
        self.assertEqual(get_minister_wechat("office"), "test_office")
        self.contacts["office"] = "new_test_office"
        replacement = self.path.with_suffix(".tmp")
        replacement.write_text(json.dumps({"minister_wechat": self.contacts}), encoding="utf-8-sig")
        replacement.replace(self.path)
        self.assertEqual(get_minister_wechat("office"), "new_test_office")

    def test_missing_or_invalid_config_does_not_admit_or_change_accounts(self):
        bad_configs = [
            None, "not-json", '[]', '{}', '{"minister_wechat": []}',
            '{"minister_wechat": {"office": "  "}}',
            '{"minister_wechat": {"office": 123456}}',
            '{"minister_wechat": {"office": "bad\\ncontact"}}',
        ]
        for content in bad_configs:
            with self.subTest(config=content), self.database() as (db, candidate):
                if content is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self.path.write_text(content, encoding="utf-8")
                db.add(User(uid=candidate.uid, passwd="original", role_id=7))
                db.commit()
                with self.assertRaises(HTTPException) as error:
                    final_accept(FinalAcceptRequest(uid=candidate.uid, department="office"), db, True)
                self.assertEqual(error.exception.status_code, 503)
                db.expire_all()
                self.assertFalse(db.get(Recruitment, candidate.uid).is_admitted)
                self.assertIsNone(db.get(Recruitment, candidate.uid).admission_time)
                self.assertIsNone(db.get(Member, candidate.uid))
                self.assertEqual(db.get(User, candidate.uid).passwd, "original")
                self.assertEqual(db.get(User, candidate.uid).role_id, 7)
                self.send.assert_not_called()

    def test_invalid_department_does_not_admit(self):
        for department in ["", "unknown"]:
            with self.subTest(department=department), self.database() as (db, candidate):
                with self.assertRaises(HTTPException) as error:
                    final_accept(FinalAcceptRequest(uid=candidate.uid, department=department), db, True)
                self.assertEqual(error.exception.status_code, 400)
                self.assertFalse(db.get(Recruitment, candidate.uid).is_admitted)
                self.assertIsNone(db.get(Member, candidate.uid))
                self.assertIsNone(db.get(User, candidate.uid))
                self.send.assert_not_called()

    def test_existing_admission_prerequisites_keep_their_status_codes(self):
        with self.database() as (db, candidate):
            with self.assertRaises(HTTPException) as error:
                final_accept(FinalAcceptRequest(uid="missing", department="office"), db, True)
            self.assertEqual(error.exception.status_code, 404)
            for field in ["first_round_passed", "second_round_passed"]:
                with self.subTest(field=field):
                    setattr(candidate, field, False)
                    db.commit()
                    with self.assertRaises(HTTPException) as error:
                        final_accept(FinalAcceptRequest(uid=candidate.uid, department="office"), db, True)
                    self.assertEqual(error.exception.status_code, 400)
                    self.assertFalse(candidate.is_admitted)
                    setattr(candidate, field, True)
                    db.commit()
            self.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
