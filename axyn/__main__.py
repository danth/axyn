from axyn.client import AxynClient
from importlib.metadata import PackageNotFoundError, version
from opentelemetry.trace import set_tracer_provider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import os


def _configure_tracing():
    """
    Configure OpenTelemetry tracing.

    This sets where tracing output is sent, based on environment variables
    such as ``OTEL_EXPORTER_OTLP_ENDPOINT``. By default, it is not sent
    anywhere.
    """

    resource_attributes = {"service.name": "axyn"}

    try:
        resource_attributes["service.version"] = version("axyn")
    except PackageNotFoundError:
        pass

    resource = Resource.create(resource_attributes)

    processor = BatchSpanProcessor(OTLPSpanExporter())

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    set_tracer_provider(provider)


def launch():
    """
    Start Axyn.

    The login token is taken from the environment variable ``DISCORD_TOKEN``.
    """

    _configure_tracing()

    AxynClient().run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    launch()
