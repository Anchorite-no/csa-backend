import base64
import random
import string

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_config
from misc.miniapp import get_miniapp_code
from models import get_db
from models.register import Register

router = APIRouter()


def generate_seid() -> str:
    # generate 24 random characters
    return "".join(random.choices(string.ascii_letters + string.digits, k=24))


class NewSession(BaseModel):
    seid: str
    uid: str
    nick: str


class ResponseMiniappCode(BaseModel):
    code: bytes


class SubmitMiniappInfo(BaseModel):
    seid: str
    code: str


class RequestMiniappStatus(BaseModel):
    seid: str


class SubmitRegister(BaseModel):
    seid: str
    email: str
    # and so on


@router.get("/new_sess")
def create_new_sess(code: str, db: Session = Depends(get_db)) -> NewSession:
    if not code:
        raise HTTPException(status_code=400, detail="Invalid code")

    # get userinfo from cas

    cas_url = "https://zjuam.zju.edu.cn/cas/oauth2.0/accessToken"
    cas_data = {
        "client_id": get_config("CAS_APP_ID"),
        "client_secret": get_config("CAS_APP_SECRET"),
        "code": code,
        "redirect_uri": get_config("CAS_REDIRECT_URI")
    }

    cas_resp = requests.get(cas_url, params=cas_data)

    if cas_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="CAS server error")

    cas_resp_json = cas_resp.json()
    access_token = cas_resp_json.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Invalid code")

    cas_url = "https://zjuam.zju.edu.cn/cas/oauth2.0/profile"
    cas_data = {
        "access_token": access_token
    }

    cas_resp = requests.get(cas_url, params=cas_data)

    if "errorcode" in cas_resp.json():
        raise HTTPException(status_code=400, detail="Invalid code")

    cas_resp_json = cas_resp.json()["attributes"]

    seid = generate_seid()
    new_register = Register(
        seid=seid,
        uid=cas_resp_json.get("CODE"),
        nick=cas_resp_json.get("NAME")
    )

    db.add(new_register)
    db.commit()

    return NewSession(seid=seid, uid=cas_resp_json.get("CODE"), nick=cas_resp_json.get("NAME"))


@router.get("/miniapp_code")
def get_miniapp_code(seid: str, db: Session = Depends(get_db())) -> ResponseMiniappCode:
    register = db.query(Register).filter(Register.seid == seid).first()
    if not register:
        raise HTTPException(status_code=404, detail="Session not found")

    code = get_miniapp_code(seid)
    code = base64.b64encode(code)

    return ResponseMiniappCode(code=code)


@router.get("/miniapp_submit")
def submit_miniapp(data: SubmitMiniappInfo, db: Session = Depends(get_db())):
    register = db.query(Register).filter(Register.seid == data.seid).first()
    if not register:
        raise HTTPException(status_code=404, detail="Session not found")

    # submit code to miniapp
    miniapp_url = "https://api.weixin.qq.com/sns/jscode2session"
    miniapp_params = {
        "appid": get_config("WEIXIN_APP_ID"),
        "secret": get_config("WEIXIN_APP_SECRET"),
        "js_code": data.code,
        "grant_type": "authorization_code"
    }

    miniapp_resp = requests.get(miniapp_url, params=miniapp_params)

    if miniapp_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Miniapp server error")

    miniapp_resp_json = miniapp_resp.json()
    openid = miniapp_resp_json.get("openid")

    if not openid:
        raise HTTPException(status_code=400, detail="Invalid code")

    register.openid = openid
    db.commit()

    return {"msg": "success"}


@router.get("/miniapp_status")
def get_miniapp_status(data: RequestMiniappStatus, db: Session = Depends(get_db())):
    register = db.query(Register).filter(Register.seid == data.seid).first()
    if not register:
        raise HTTPException(status_code=404, detail="Session not found")

    if not register.openid:
        return {"status": False}
    else:
        return {"status": True}


@router.post("/submit")
def register(data: SubmitRegister, db: Session = Depends(get_db)):
    if not data.seid:
        raise HTTPException(status_code=400, detail="Invalid seid")

    register = db.query(Register).filter(Register.seid == data.seid).first()
    if not register:
        raise HTTPException(status_code=404, detail="Session not found")

    if not data.uid or not data.nick or not data.openid:
        raise HTTPException(status_code=400, detail="Invalid userinfo")

    # process register
    # ......

    db.delete(register)
    db.commit()

    return {"msg": "success"}
