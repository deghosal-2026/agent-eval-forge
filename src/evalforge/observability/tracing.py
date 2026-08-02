"""Lightweight OpenTelemetry-compatible tracing for evaluation runs.

Creates trace contexts with parent/child span relationships and can export
to OTLP collectors — all without requiring the OpenTelemetry SDK.
"""

from __future__ import annotations

import json
import secrets
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceSpan:
    """A single span within a trace.

    Attributes:
        name: Human-readable operation name.
        span_id: Unique span identifier (hex string).
        parent_id: Span ID of the parent span, or ``None`` for the root.
        start_time: Unix timestamp of span start.
        end_time: Unix timestamp of span end (``None`` if still open).
        attributes: Key-value metadata attached to the span.
        status: One of ``"ok"`` or ``"error"``.
        events: Ordered list of event dicts (each with ``name``, ``timestamp``,
            and optional ``attributes``).
    """
    name: str
    span_id: str
    parent_id: str | None
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TraceContext:
    """A full trace context containing a trace ID and all its spans.

    Attributes:
        trace_id: Unique trace identifier (hex string).
        spans: List of :class:`TraceSpan` instances belonging to this trace.
        start_time: Unix timestamp when the trace started.
    """
    trace_id: str
    spans: list[TraceSpan] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)


class OpenTelemetryTracer:
    """Lightweight tracer that creates span trees and can export to OTLP.

    Does NOT require the ``opentelemetry-sdk`` package — it implements a
    compatible data model and serialisation on its own.

    Args:
        service_name: Logical service name for the resource (default ``"evalforge"``).
    """

    def __init__(self, service_name: str = "evalforge") -> None:
        self._spans: list[TraceSpan] = []
        self._context: TraceContext | None = None
        self._span_stack: list[TraceSpan] = []
        self._service_name = service_name

    def start_trace(self, operation: str) -> TraceContext:
        """Start a new trace with a root span for the given operation.

        Args:
            operation: Name of the root operation.

        Returns:
            The new :class:`TraceContext`.
        """
        trace_id = secrets.token_hex(16)
        self._context = TraceContext(trace_id=trace_id)
        root = self.start_span(operation)
        root.parent_id = None
        return self._context

    def start_span(self, name: str) -> TraceSpan:
        """Start a new child span under the current span (or root if none).

        Args:
            name: Span name.

        Returns:
            The new :class:`TraceSpan`.
        """
        parent_id = self._span_stack[-1].span_id if self._span_stack else None
        span = TraceSpan(
            name=name,
            span_id=secrets.token_hex(8),
            parent_id=parent_id,
            start_time=time.time(),
        )
        self._spans.append(span)
        self._span_stack.append(span)
        if self._context is not None:
            self._context.spans.append(span)
        return span

    def end_span(
        self, span: TraceSpan, status: str = "ok", attributes: dict[str, Any] | None = None
    ) -> None:
        """Finalise a span with an end timestamp, status, and optional attributes.

        Args:
            span: The :class:`TraceSpan` to finalise.
            status: Final status (``"ok"`` or ``"error"``).
            attributes: Additional attributes to merge into the span.
        """
        span.end_time = time.time()
        span.status = status
        if attributes:
            span.attributes.update(attributes)
        if self._span_stack and self._span_stack[-1].span_id == span.span_id:
            self._span_stack.pop()

    def add_event(
        self, span: TraceSpan, name: str, attributes: dict[str, Any] | None = None
    ) -> None:
        """Record a timestamped event on a span.

        Args:
            span: The target :class:`TraceSpan`.
            name: Event name.
            attributes: Optional event attributes.
        """
        event: dict[str, Any] = {
            "name": name,
            "timestamp": time.time(),
        }
        if attributes:
            event["attributes"] = attributes
        span.events.append(event)

    def set_attribute(self, span: TraceSpan, key: str, value: Any) -> None:
        """Set a key-value attribute on a span.

        Args:
            span: The target :class:`TraceSpan`.
            key: Attribute name.
            value: Attribute value.
        """
        span.attributes[key] = value

    def export_otlp(self, endpoint: str) -> None:
        """Export spans to an OTLP-compatible HTTP collector.

        Constructs an ``OTLP `` resourceSpans payload and POSTs it as JSON
        to *endpoint*.

        Args:
            endpoint: Full URL of the OTLP HTTP collector
                (e.g. ``http://localhost:4318/v1/traces``).
        """
        if not self._spans:
            return
        trace_id = self._context.trace_id if self._context else secrets.token_hex(16)
        spans_payload = []
        for span in self._spans:
            if span.end_time is None:
                continue
            spans_payload.append(
                {
                    "traceId": trace_id,
                    "spanId": span.span_id,
                    "parentSpanId": span.parent_id or "",
                    "name": span.name,
                    "kind": 1,
                    "startTimeUnixNano": str(int(span.start_time * 1e9)),
                    "endTimeUnixNano": str(int(span.end_time * 1e9)),
                    "attributes": [
                        {"key": k, "value": {"stringValue": str(v)}}
                        for k, v in span.attributes.items()
                    ],
                    "status": {"code": 1 if span.status == "ok" else 2},
                }
            )
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": self._service_name},
                            }
                        ]
                    },
                    "scopeSpans": [{"spans": spans_payload}],
                }
            ]
        }
        data = json.dumps(payload).encode("utf-8")
        try:
            req = urllib.request.Request(  # noqa: S310
                endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
        except Exception:  # noqa: S110
            pass

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trace to a plain dict.

        Returns:
            Dict with ``trace_id``, ``service_name``, and ``spans``.
        """
        spans_data = []
        for span in self._spans:
            duration = (
                round((span.end_time - span.start_time) * 1000, 2)
                if span.end_time is not None
                else None
            )
            spans_data.append(
                {
                    "name": span.name,
                    "span_id": span.span_id,
                    "parent_id": span.parent_id,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "duration_ms": duration,
                    "attributes": span.attributes,
                    "status": span.status,
                    "events": span.events,
                }
            )
        return {
            "trace_id": self._context.trace_id if self._context else "",
            "service_name": self._service_name,
            "spans": spans_data,
        }

    def to_json(self) -> str:
        """Serialize the trace to a JSON string.

        Returns:
            Indented JSON representation of :meth:`to_dict`.
        """
        return json.dumps(self.to_dict(), indent=2)

    @property
    def context(self) -> TraceContext | None:
        """Return the current :class:`TraceContext`, or ``None``."""
        return self._context
