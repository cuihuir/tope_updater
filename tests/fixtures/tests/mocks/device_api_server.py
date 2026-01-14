"""Mock device-api server for testing callbacks."""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Mock Device-API")

# Store received callbacks
callbacks = []

logger = logging.getLogger("mock-device-api")


@app.post("/api/v1.0/ota/report")
async def ota_report(request: Request):
    """Receive OTA status callback."""
    body = await request.json()
    callbacks.append(body)

    logger.info(f"📨 Received callback: {body}")

    return JSONResponse(content={
        "code": 200,
        "msg": "success",
        "data": None
    })


@app.get("/api/v1.0/ota/callbacks")
async def get_callbacks():
    """Return all received callbacks."""
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "count": len(callbacks),
            "callbacks": callbacks
        }
    }


@app.delete("/api/v1.0/ota/callbacks")
async def clear_callbacks():
    """Clear callback history."""
    callbacks.clear()
    return {
        "code": 200,
        "msg": "success",
        "data": None
    }


def run_mock_server(port: int = 9080):
    """Run mock server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run_mock_server()
