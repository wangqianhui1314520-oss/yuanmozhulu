"""
统一响应格式 - 全局规范

所有 API 端点返回此格式:
{
  "code": 200,    # 200成功 400参数错误 403权限不足 500服务异常
  "msg": "success",
  "data": {}
}
"""
from __future__ import annotations
from typing import Any, Optional


class ApiResponse:
    """统一响应构建器"""

    @staticmethod
    def success(data: Any = None, msg: str = "success") -> dict:
        return {"code": 200, "msg": msg, "data": data}

    @staticmethod
    def error(code: int, msg: str, data: Any = None) -> dict:
        return {"code": code, "msg": msg, "data": data}

    @staticmethod
    def bad_request(msg: str = "请求参数有误") -> dict:
        return {"code": 400, "msg": msg, "data": None}

    @staticmethod
    def forbidden(msg: str = "指令不合法或权限不足") -> dict:
        return {"code": 403, "msg": msg, "data": None}

    @staticmethod
    def not_found(msg: str = "资源不存在") -> dict:
        return {"code": 404, "msg": msg, "data": None}

    @staticmethod
    def server_error(msg: str = "服务器内部异常") -> dict:
        return {"code": 500, "msg": msg, "data": None}
