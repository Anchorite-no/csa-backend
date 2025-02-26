import io
from datetime import datetime, timedelta
from functools import cache
from typing import Tuple

import requests
from PIL import Image

from config import get_config


@cache
def fetch_access_token() -> Tuple[str, int]:
    app_id = get_config("WEIXIN_APP_ID")
    app_secret = get_config("WEIXIN_APP_SECRET")

    response = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        {"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
    )

    data = response.json()
    access_token = data["access_token"]
    expires = datetime.now() + timedelta(seconds=data["expires_in"])
    expires = int(expires.timestamp())

    return access_token, expires


def get_access_token(refresh: bool = False) -> str:
    token, expires = fetch_access_token()

    if refresh or expires <= datetime.now().timestamp():
        fetch_access_token.cache_clear()
        token, expires = fetch_access_token()

    return token


def request_code(seid, token):
    data = {
        "page": "pages/reg/reg",
        "scene": "seid=" + str(seid),
        "check_path": True,
        "env_version": "release",
    }

    response = requests.post(
        "https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token=" + token,
        json=data,
        )

    return response


def get_miniapp_code(seid) -> bytes:
    token = get_access_token()
    response = request_code(seid, token)

    try:
        err = response.json()
        if err["errcode"] == 40001:
            token = get_access_token(True)
            response = request_code(seid, token)
    except:
        pass

    im = Image.open(io.BytesIO(response.content))
    x, y = im.size
    im = im.resize((128, round(128 * y / x)))
    out = io.BytesIO()
    im.save(out, quality=75, format='jpeg')

    return out.getvalue()
