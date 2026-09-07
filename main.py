from fastapi import FastAPI

from misc.model import create_admin
from misc.recruit_deadline import initialize_recruit_deadline
from models import Base, engine
from routes import init_app_routes


app = FastAPI(title="CsaBackend", version="0.1.0")

init_app_routes(app)

Base.metadata.create_all(bind=engine)
initialize_recruit_deadline()
create_admin()
