from fastapi import FastAPI

app = FastAPI(title="VocalLedger")

@app.get("/")
def root():
    return {"status": "VocalLedger is running"}