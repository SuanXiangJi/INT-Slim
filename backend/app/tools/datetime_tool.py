# -*- coding: utf-8 -*-
"""
DateTime Tool - 日期时间查询和计算
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.tools.base import BaseTool, register_tool

logger = logging.getLogger(__name__)


@register_tool
class DateTimeTool(BaseTool):
    """日期时间工具"""

    @property
    def id(self) -> str:
        return "datetime"

    @property
    def name(self) -> str:
        return "日期时间"

    @property
    def description(self) -> str:
        return "查询当前时间、进行日期时间计算、转换时区。支持的 operation: 'now'(当前时间), 'diff'(计算差值), 'add'(加时间), 'format'(格式化), 'parse'(解析字符串)。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["now", "diff", "add", "format", "parse"],
                    "description": "要执行的操作"
                },
                "timezone": {
                    "type": "string",
                    "description": "时区名称，如 'Asia/Shanghai', 'UTC', 'America/New_York'",
                    "default": "UTC"
                },
                "datetime_str": {
                    "type": "string",
                    "description": "日期时间字符串，用于 parse/diff/add/format"
                },
                "format": {
                    "type": "string",
                    "description": "日期格式，如 '%Y-%m-%d %H:%M:%S'",
                    "default": "%Y-%m-%d %H:%M:%S"
                },
                "delta_days": {
                    "type": "integer",
                    "description": "加减天数（add 时使用）",
                    "default": 0
                },
                "delta_hours": {
                    "type": "integer",
                    "description": "加减小时数（add 时使用）",
                    "default": 0
                },
                "delta_minutes": {
                    "type": "integer",
                    "description": "加减分钟数（add 时使用）",
                    "default": 0
                }
            },
            "required": ["operation"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        op = params["operation"]
        tz_name = params.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return {"success": False, "error": f"Unknown timezone: {tz_name}"}

        try:
            if op == "now":
                now = datetime.now(tz)
                fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
                return {
                    "success": True,
                    "datetime": now.strftime(fmt),
                    "timezone": tz_name,
                    "iso": now.isoformat(),
                    "timestamp": int(now.timestamp()),
                    "weekday": now.strftime("%A"),
                }
            elif op == "diff":
                dt1_str = params.get("datetime_str")
                if not dt1_str:
                    return {"success": False, "error": "datetime_str required"}
                dt1 = datetime.fromisoformat(dt1_str.replace("Z", "+00:00"))
                dt2 = datetime.now(tz)
                delta = dt2 - dt1
                return {
                    "success": True,
                    "from": dt1.isoformat(),
                    "to": dt2.isoformat(),
                    "days": delta.days,
                    "seconds": int(delta.total_seconds()),
                    "human": str(delta).split('.')[0],
                }
            elif op == "add":
                dt_str = params.get("datetime_str")
                if not dt_str:
                    dt_str = datetime.now(tz).isoformat()
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                delta = timedelta(
                    days=params.get("delta_days", 0),
                    hours=params.get("delta_hours", 0),
                    minutes=params.get("delta_minutes", 0),
                )
                new_dt = dt + delta
                return {
                    "success": True,
                    "original": dt.isoformat(),
                    "result": new_dt.isoformat(),
                    "delta": str(delta),
                }
            elif op == "format":
                dt_str = params.get("datetime_str")
                if not dt_str:
                    dt_str = datetime.now(tz).isoformat()
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
                return {"success": True, "formatted": dt.strftime(fmt)}
            elif op == "parse":
                dt_str = params.get("datetime_str")
                if not dt_str:
                    return {"success": False, "error": "datetime_str required"}
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return {
                        "success": True,
                        "iso": dt.isoformat(),
                        "timestamp": int(dt.timestamp()),
                    }
                except ValueError:
                    return {"success": False, "error": f"Cannot parse: {dt_str}"}
            else:
                return {"success": False, "error": f"Unknown operation: {op}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
