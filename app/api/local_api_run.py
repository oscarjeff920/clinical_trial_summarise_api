import uvicorn

from app.api.api_config import get_api_settings
from app.api.app import medical_docs_api

if __name__ == "__main__":
    api_config = get_api_settings()

    uvicorn.run(
        medical_docs_api,
        host=api_config.API_HOST,
        port=api_config.API_PORT,
        reload=True
    )