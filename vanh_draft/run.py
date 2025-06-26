import uvicorn

if __name__ == "__main__":
    uvicorn.run("fast_api_user_request:app", host="0.0.0.0", port=8010, reload=True)
