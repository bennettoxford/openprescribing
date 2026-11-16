import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


# BatchSpanProcessor doesn't work well with Gunicorn, but we can work around its
# limitations with a post-fork hook. For more information, see:
# https://opentelemetry-python.readthedocs.io/en/latest/examples/fork-process-model/README.html
def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    source_commit_id = os.environ["SOURCE_COMMIT_ID"]
    resource = Resource.create(
        attributes={
            "service.name": "openprescribing",
            "service.version": source_commit_id,
        }
    )
    trace.set_tracer_provider(TracerProvider(resource=resource))
    span_processor = BatchSpanProcessor(OTLPSpanExporter())
    trace.get_tracer_provider().add_span_processor(span_processor)
    from opentelemetry.instrumentation.auto_instrumentation import (  # noqa: F401
        sitecustomize,
    )
