from fastapi import FastAPI

app = FastAPI(title="Mini Kanban API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
