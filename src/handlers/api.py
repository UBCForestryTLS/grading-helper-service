import os

from mangum import Mangum

from src.api.app import create_app

app = create_app()
stage = os.environ.get("STAGE", "")
handler = Mangum(
    app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else "/"
)
