import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from src.utils.db import init_db, engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database for NewFit Web Application...")
    await init_db(engine)
    logger.info("NewFit Web Application started successfully.")
    yield
    logger.info("NewFit Web Application shutting down...")

app = FastAPI(
    title="NewFit Web Application",
    description="Web API and Web App interface for NewFit ecosystem",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NewFit - Экосистема спорта и бьюти</title>
        <style>
            :root {
                --primary: #4f46e5;
                --primary-hover: #4338ca;
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text: #f8fafc;
                --text-muted: #94a3b8;
                --accent: #10b981;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                min-height: 100vh;
                align-items: center;
                justify-content: center;
            }
            .container {
                max-width: 600px;
                width: 90%;
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 32px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
                text-align: center;
                border: 1px solid #334155;
            }
            .badge {
                display: inline-block;
                background: rgba(16, 185, 129, 0.2);
                color: var(--accent);
                font-size: 14px;
                font-weight: 600;
                padding: 6px 16px;
                border-radius: 20px;
                margin-bottom: 20px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            }
            h1 {
                font-size: 32px;
                margin: 0 0 12px 0;
                background: linear-gradient(135deg, #a5b4fc 0%, #818cf8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            p {
                color: var(--text-muted);
                line-height: 1.6;
                font-size: 16px;
                margin-bottom: 28px;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                margin-bottom: 28px;
                text-align: left;
            }
            .grid-item {
                background: rgba(255, 255, 255, 0.03);
                padding: 14px;
                border-radius: 10px;
                border: 1px solid #334155;
                font-size: 14px;
            }
            .grid-item strong {
                display: block;
                color: var(--text);
                margin-bottom: 4px;
            }
            .btn {
                display: inline-block;
                background-color: var(--primary);
                color: #ffffff;
                text-decoration: none;
                font-weight: 600;
                padding: 12px 28px;
                border-radius: 10px;
                transition: background-color 0.2s;
            }
            .btn:hover {
                background-color: var(--primary-hover);
            }
            footer {
                margin-top: 24px;
                font-size: 13px;
                color: var(--text-muted);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="badge">● Web-версия запущенa</div>
            <h1>NewFit Web Platform</h1>
            <p>Добро пожаловать в веб-платформу NewFit — единую экосистему для записи на тренировки (Фитнес, Большой теннис, Падл) и услуги бьюти-сферы.</p>

            <div class="grid">
                <div class="grid-item">
                    <strong>⭐ Тренеры & Специалисты</strong>
                    Запись, расписание и модерация
                </div>
                <div class="grid-item">
                    <strong>👤 Клиенты</strong>
                    Поиск по городам и фильтры
                </div>
                <div class="grid-item">
                    <strong>📅 Расписание</strong>
                    Управление слотами и датами
                </div>
                <div class="grid-item">
                    <strong>💳 B2B Подписки</strong>
                    Управление тарифами
                </div>
            </div>

            <a href="/docs" class="btn">Открыть Swagger API Documentation</a>
        </div>
        <footer>&copy; NewFit Ecosystem. Все права защищены.</footer>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok", "app": "NewFit Web"})
