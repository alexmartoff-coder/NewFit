import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.utils.db import init_db, engine

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates", "stitch_design_system")
if not os.path.exists(TEMPLATES_DIR):
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates", "stitch_newfin_bilibin_design_system")

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

# Mount static files directory if it exists
if os.path.exists(TEMPLATES_DIR):
    app.mount("/design-system", StaticFiles(directory=TEMPLATES_DIR), name="design-system")

def render_screen(folder_name: str) -> HTMLResponse:
    file_path = os.path.join(TEMPLATES_DIR, folder_name, "code.html")
    if not os.path.exists(file_path):
        # Fallback if folder_name doesn't have code.html directly
        file_path = os.path.join(TEMPLATES_DIR, folder_name)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"Screen '{folder_name}' not found")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok", "app": "NewFit Web"})

# --- Main App Routes Linked to SPECIFICATION.md ---

@app.get("/", response_class=HTMLResponse)
async def welcome_page():
    """Welcome / Role Selection Screen (Flow 1)"""
    return render_screen("_14")

@app.get("/welcome-alt", response_class=HTMLResponse)
async def welcome_alt_page():
    """Alternative Welcome Screen"""
    return render_screen("_15")

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page():
    """Specialists Catalog Screen (Flow 3)"""
    return render_screen("newfit")

@app.get("/specialist", response_class=HTMLResponse)
@app.get("/specialist/{specialist_id}", response_class=HTMLResponse)
async def specialist_profile_page(specialist_id: str = None):
    """Specialist Public Profile Screen"""
    return render_screen("_1")

@app.get("/booking", response_class=HTMLResponse)
@app.get("/booking/{slot_id}", response_class=HTMLResponse)
async def booking_page(slot_id: str = None):
    """Slot Booking Screen (Flow 3)"""
    return render_screen("_2")

@app.get("/pro/schedule", response_class=HTMLResponse)
async def pro_schedule_page():
    """Pro Specialist Schedule Screen (Flow 4)"""
    return render_screen("_3")

@app.get("/pro/clients", response_class=HTMLResponse)
async def pro_clients_page():
    """Pro Specialist My Clients Screen"""
    return render_screen("_4")

@app.get("/pro/profile/edit", response_class=HTMLResponse)
async def pro_profile_edit_page():
    """Pro Profile Edit Screen (Flow 2)"""
    return render_screen("_5")

@app.get("/pro/schedule/generate", response_class=HTMLResponse)
async def pro_schedule_generate_page():
    """Pro Slot Generator Screen (Flow 4)"""
    return render_screen("_6")

@app.get("/pro/unlock", response_class=HTMLResponse)
async def pro_unlock_page():
    """Pro Subscription B2B Gate Screen (Flow 5)"""
    return render_screen("pro")

@app.get("/client/favorites", response_class=HTMLResponse)
async def client_favorites_page():
    """Client Favorites Screen"""
    return render_screen("_11")

@app.get("/client/bookings", response_class=HTMLResponse)
async def client_bookings_page():
    """Client My Bookings Screen"""
    return render_screen("_12")

@app.get("/client/profile", response_class=HTMLResponse)
async def client_profile_page():
    """Client Profile Screen"""
    return render_screen("_13")

@app.get("/client/profile/view", response_class=HTMLResponse)
async def client_profile_view_page():
    """Client Profile Alternate Screen"""
    return render_screen("_16")

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page():
    """Admin Dashboard Screen"""
    return render_screen("_7")

@app.get("/admin/subscriptions", response_class=HTMLResponse)
async def admin_subscriptions_page():
    """Admin Subscriptions Control Screen"""
    return render_screen("_8")

@app.get("/admin/moderation", response_class=HTMLResponse)
async def admin_moderation_page():
    """Admin Moderation Queue Screen"""
    return render_screen("_9")

@app.get("/admin/devtools", response_class=HTMLResponse)
async def admin_devtools_page():
    """Admin Developer Tools Screen"""
    return render_screen("_10")

@app.get("/shader", response_class=HTMLResponse)
async def shader_page():
    """Shader Visual Screen"""
    return render_screen("shader")

# --- Direct Access Route for Any Design System Screen Folder ---

@app.get("/screen/{folder_name}", response_class=HTMLResponse)
async def direct_screen_page(folder_name: str):
    return render_screen(folder_name)
