import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.auth import (
    CreateUserRequest, ForceChangePasswordRequest, UpdateUserRequest,
    create_user, force_change_password, get_current_user, update_user,
)
from database import Base
from models import User
from services.auth import bootstrap_admin, create_access_token, verify_password


def fake_request(path):
    return Request({"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""})


class DefaultAdminTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        env = {k: v for k, v in os.environ.items() if k != "ADMIN_PASSWORD"}
        with patch.dict(os.environ, env, clear=True), patch("database.save_setting") as save:
            bootstrap_admin(self.db)
            self.save = save
        self.admin = self.db.query(User).one()

    def tearDown(self):
        self.db.close()

    def token(self, user):
        return create_access_token({"sub": str(user.id), "role": user.role})

    def test_default_password_forces_change_and_login_mode(self):
        self.assertTrue(verify_password("Admin", self.admin.hashed_password))
        self.assertTrue(self.admin.must_change_password)
        self.save.assert_called_with("multi_user_mode", "true")

    def test_env_password_does_not_force_change(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "Str0ng-pass!"}), patch("database.save_setting"):
            bootstrap_admin(db)
        self.assertFalse(db.query(User).one().must_change_password)

    def test_other_endpoints_blocked_until_changed(self):
        with self.assertRaises(HTTPException) as exc:
            get_current_user(token=self.token(self.admin), db=self.db, request=fake_request("/api/collection"))
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail, "password_change_required")
        user = get_current_user(token=self.token(self.admin), db=self.db, request=fake_request("/api/auth/me"))
        self.assertEqual(user.id, self.admin.id)

    def test_force_change_rejects_weak_then_unblocks(self):
        for bad in ("Admin", "short"):
            with self.assertRaises(HTTPException):
                force_change_password(ForceChangePasswordRequest(new_password=bad), self.admin, self.db)
        force_change_password(ForceChangePasswordRequest(new_password="Nouveau-mdp-9"), self.admin, self.db)
        self.assertFalse(self.admin.must_change_password)
        get_current_user(token=self.token(self.admin), db=self.db, request=fake_request("/api/collection"))

    def test_admin_created_and_reset_accounts_must_change(self):
        self.admin.must_change_password = False
        create_user(CreateUserRequest(username="luca2", password="temp1234"), self.admin, self.db)
        u = self.db.query(User).filter(User.username == "luca2").one()
        self.assertTrue(u.must_change_password)
        u.must_change_password = False
        update_user(u.id, UpdateUserRequest(password="autre-temp"), self.admin, self.db)
        self.db.refresh(u)
        self.assertTrue(u.must_change_password)


if __name__ == "__main__":
    unittest.main()
