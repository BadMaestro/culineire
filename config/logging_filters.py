from __future__ import annotations

import logging
import re


class RedactSensitiveDataFilter(logging.Filter):
    sensitive_patterns = (
        re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*([^\s,;]+)"),
        re.compile(r"(?i)(secret|token|api[_-]?key|sessionid|csrftoken)\s*[:=]\s*([^\s,;]+)"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self.sensitive_patterns:
            message = pattern.sub(r"\1=[REDACTED]", message)

        if message != record.getMessage():
            record.msg = message
            record.args = ()

        return True
