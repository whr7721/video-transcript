"""Versioned provenance and a small, explicit task-handler registry."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class FileSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    kind: Literal['local_file'] = 'local_file'
    original_name: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    size_bytes: int = Field(gt=0, le=1_000_000_000)


class TaskHandlers:
    def __init__(self):
        self._handlers = {}

    def register(self, kind, handler):
        if kind in self._handlers:
            raise ValueError('来源处理器不能重复注册')
        self._handlers[kind] = handler

    def resolve(self, task):
        source = task.get('source') or {}
        return self._handlers.get(source.get('kind'))

    def kinds(self):
        return sorted(self._handlers)
