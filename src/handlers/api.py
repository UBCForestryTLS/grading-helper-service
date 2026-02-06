from mangum import Mangum

from src.api.app import create_app

app = create_app()
handler = Mangum(app, lifespan="off")
