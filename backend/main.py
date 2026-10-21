# -*- coding: utf-8 -*-
"""资产经营公司管理系统 - FastAPI 入口"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
from db import seed
from routers import approvals, assessment, auth_router, companies, dashboard, platform, reminders, transfer

app = FastAPI(title="资产经营公司管理系统", version="1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if p == "/" or p.startswith("/assets"):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(companies.router)
app.include_router(reminders.router)
app.include_router(approvals.router)
app.include_router(assessment.router)
app.include_router(transfer.router)
app.include_router(platform.router)

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="static")


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": f"服务器内部错误: {exc}"})


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.on_event("startup")
def startup():
    seed()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
