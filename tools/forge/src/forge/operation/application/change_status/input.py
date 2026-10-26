"""Входные контракты остановки и продолжения операции."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopOperationInput:
    """Беклог операции и причина остановки."""

    operation_path: str
    reason: str


@dataclass(frozen=True)
class ResumeOperationInput:
    """Беклог операции и согласие на удаления, которое даётся при продолжении."""

    operation_path: str
    allow_drop: bool = False
