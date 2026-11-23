# -*- coding: utf-8 -*-
"""QQ 官方机器人通知

接入方式：QQ 开放平台官方机器人 API
- 获取凭据：POST https://bots.qq.com/app/getAppAccessToken
- 发送私信：POST https://api.sgroup.qq.com/v2/users/{openid}/messages
  （官方 API 以 openid 标识接收人，需用户曾与该机器人交互过才能获得 openid）
"""
import time
import logging
import requests

TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
MSG_URL = "https://api.sgroup.qq.com/v2/users/{openid}/messages"

# token 缓存：{"token": str, "expires_at": float}
_token_cache = {"token": None, "expires_at": 0}


def _get_access_token(app_id, app_secret):
    """获取（带缓存）机器人 access token"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"], None

    try:
        resp = requests.post(
            TOKEN_URL,
            json={"appId": app_id, "clientSecret": app_secret},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            return None, f"获取token失败：HTTP {resp.status_code} {data}"
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 7200))
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + expires_in
        return token, None
    except Exception as e:
        return None, f"获取token异常：{e}"


def send_message(content):
    """发送 QQ 私信通知，返回 (success, message)"""
    import db
    cfg = db.get_notify_config()
    if not cfg["enabled"]:
        return False, "通知未启用"
    if not (cfg["app_id"] and cfg["app_secret"] and cfg["user_openid"]):
        return False, "通知配置不完整（appId/appSecret/openid）"

    token, err = _get_access_token(cfg["app_id"], cfg["app_secret"])
    if err:
        logging.warning(f"QQ通知获取token失败：{err}")
        return False, err

    try:
        resp = requests.post(
            MSG_URL.format(openid=cfg["user_openid"]),
            headers={"Authorization": f"QQBot {token}"},
            json={
                "msg_type": 0,  # 文本消息
                "content": content,
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logging.info("QQ通知发送成功")
            return True, "ok"
        err_msg = f"发送失败：HTTP {resp.status_code} {resp.text[:300]}"
        logging.warning(f"QQ通知{err_msg}")
        return False, err_msg
    except Exception as e:
        logging.warning(f"QQ通知发送异常：{e}")
        return False, f"发送异常：{e}"
