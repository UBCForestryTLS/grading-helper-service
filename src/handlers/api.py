import os

from mangum import Mangum

from src.api.app import create_app

from src.core.observability import logger, metrics, tracer

app = create_app()
stage = os.environ.get("STAGE", "")
handler_app = Mangum(
    app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else "/"
)


@logger.inject_lambda_context(log_event=False)
@metrics.log_metrics
@tracer.capture_lambda_handler
def handler(event: dict, context: object) -> dict:
    return handler_app(event, context)
