import uvicorn

from api.api_config import get_api_settings
from api.endpoints import medical_docs_api

if __name__ == "__main__":
    api_config = get_api_settings()

    uvicorn.run(
        "__main__:medical_docs_api",
        host=api_config.API_HOST,
        port=api_config.API_PORT,
        reload=True,
    )
