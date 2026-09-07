"""Loopback-only integration fixture; never used as the production app."""

import os

from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import get_db
from routes.admin import set_recruit_deadline
from routes.recruit import get_deadline, confirm_recruit, get_recruitment_options
import routes.recruit as recruit_routes

# Successful application tests must never contact real recipients.
recruit_routes.send_dingtalk_message_to_user = lambda **kwargs: True

engine = create_engine(
    os.environ["CSA_DEADLINE_TEST_DB_URL"], connect_args={"check_same_thread": False}
)
sessions = sessionmaker(bind=engine)
app = FastAPI()


def test_db():
    with sessions() as db:
        yield db


def test_admin(x_test_key: str = Header(default="")):
    if x_test_key != "isolated-deadline-test":
        raise HTTPException(status_code=401)


app.dependency_overrides[get_db] = test_db
app.add_api_route("/deadline", get_deadline, methods=["GET"])
app.add_api_route(
    "/deadline", set_recruit_deadline, methods=["POST"],
    dependencies=[Depends(test_admin)],
)
app.add_api_route("/recruit", confirm_recruit, methods=["POST"])
app.add_api_route("/options", get_recruitment_options, methods=["GET"])


@app.middleware("http")
async def identify_worker(request, call_next):
    response = await call_next(request)
    response.headers["X-Test-Worker"] = str(os.getpid())
    return response
