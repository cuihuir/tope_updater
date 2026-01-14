"""Mock package server for testing downloads."""

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="Mock Package Server")

PACKAGES_DIR = Path(__file__).parent.parent / "fixtures" / "packages"


@app.get("/download/{filename}")
async def download_package(filename: str):
    """Serve test package."""
    package_path = PACKAGES_DIR / filename

    if not package_path.exists():
        return Response(
            content='{"code": 404, "msg": "Package not found"}',
            status_code=404,
            media_type="application/json"
        )

    return FileResponse(
        path=package_path,
        media_type="application/zip",
        filename=filename
    )


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="info")
