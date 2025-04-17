from fastapi import FastAPI, Request, Depends, Form, HTTPException, status, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from database import engine, SessionLocal, Base
from authlib.integrations.starlette_client import OAuth, OAuthError
from models import User
from typing import Optional
import auth
import models
import httpx
import datetime
import os
import uuid
from cachetools import TTLCache
import time

# ---------------------------
# Initialize App and Database
# ---------------------------
Base.metadata.create_all(bind=engine)
app = FastAPI()

# Middleware for session management
app.add_middleware(SessionMiddleware, secret_key="usgkfjha;i738353849etewn9n#ewrw")

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

import ssl

# Disable SSL verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# OAuth Configuration
oauth = OAuth()
oauth.config = {}
oauth.register(
    name='google',
    client_id='client-id',
    client_secret='client-secrets',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    # client_kwargs={'scope': 'openid email profile'}
    client_kwargs={'scope': 'openid email profile https://www.googleapis.com/auth/userinfo.profile'}

)

# oauth.register(
    # name='facebook',
    # client_id='client-id',
    # client_secret='client-secrets',
    # authorize_url='https://www.facebook.com/v12.0/dialog/oauth',
    # authorize_params=None,
    # access_token_url='https://graph.facebook.com/v12.0/oauth/access_token',
    # access_token_params=None,
    # client_kwargs={'scope': 'email public_profile'},
# )
oauth.register(
    name='facebook',
    client_id="1632434233489401",
    client_secret="a258e9f991232ed24854d0fc5dbfecd3",
    authorize_url="https://www.facebook.com/v12.0/dialog/oauth",
    authorize_params=None,
    access_token_url="https://graph.facebook.com/v12.0/oauth/access_token",
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri="http://localhost:8000/facebook/callback",  # Ensure this matches your OAuth settings
    client_kwargs={
        "scope": "email public_profile"
    }
)
# oauth = OAuth()
# oauth.register(
    # name='google',
    # client_id=GOOGLE_CLIENT_ID,
    # client_secret=GOOGLE_CLIENT_SECRET,
    # authorize_url='https://accounts.google.com/o/oauth2/auth',
    # authorize_params=None,
    # access_token_url='https://accounts.google.com/o/oauth2/token',
    # access_token_params=None,
    # client_kwargs={'scope': 'openid email profile'},
    # server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    # client_cls=httpx.AsyncClient,
    # client_kwargs={
        # "verify": False,  # Disable SSL verification
        # "timeout": 30.0,   # Increase timeout to avoid async issues
    # }
# )
# ---------------------------
# Rate Limiter Configuration (In-Memory)
# ---------------------------
rate_limit = {
    "requests": {},
    "limit": 1000,             # Max requests per window
    "window_seconds": 60    # Time window in seconds
}

# ---------------------------
# Caching setup
# ---------------------------
binance_cache = TTLCache(maxsize=50, ttl=60)   # Cache for Binance data (TTL = 60 seconds)
weather_cache = TTLCache(maxsize=1, ttl=300)   # Cache for weather data (TTL = 300 seconds)

# ---------------------------
# Dependencies
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------
# Dependency: Get Current User (Optional)
# ---------------------------
def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    token = request.cookies.get("access_token")
    if token:
        payload = auth.decode_access_token(token)
        if payload:
            user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
            return user
    return None

# ---------------------------
# Dependency: Get Current User (Required)
# ---------------------------
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = auth.decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------------------------
# Standard Endpoints
# ---------------------------
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, user: Optional[models.User] = Depends(get_current_user_optional)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request, user: Optional[models.User] = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("register.html", {"request": request, "user": user})

@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request, 
    username: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    if db.query(models.User).filter(models.User.email == email).first():
        return templates.TemplateResponse("register.html", {"request": request, "error": "User already exists", "user": None})
    hashed_password = auth.get_password_hash(password)
    new_user = models.User(username=username, email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, user: Optional[models.User] = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "user": user})

@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "user": None})
    token = auth.create_access_token({"user_id": user.id})
    response = RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request, user: models.User = Depends(get_current_user)):
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


# ---------------------------
# Rate Limiter Middleware
# ---------------------------
async def rate_limiter(request: Request):
    """Simple in-memory rate limiter based on IP"""
    client_ip = request.client.host
    now = time.time()

    if client_ip not in rate_limit["requests"]:
        rate_limit["requests"][client_ip] = []

    # Clean up old requests
    rate_limit["requests"][client_ip] = [
        t for t in rate_limit["requests"][client_ip] if t > now - rate_limit["window_seconds"]
    ]

    if len(rate_limit["requests"][client_ip]) >= rate_limit["limit"]:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    rate_limit["requests"][client_ip].append(now)

# ---------------------------
# Endpoints
# ---------------------------
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: User = Depends(get_current_user)):
    await rate_limiter(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/coins", response_class=HTMLResponse)
async def coins(
    request: Request, 
    page: int = Query(1, alias="page", gt=0), 
    limit: int = Query(10, le=50),
    user: User = Depends(get_current_user)
):
    """Paginated and cached coin data"""
    await rate_limiter(request)

    cache_key = f"coins_{page}_{limit}"
    if cache_key in binance_cache:
        coins_data = binance_cache[cache_key]
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://data-api.binance.vision/api/v3/ticker/24hr")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error fetching coin data")

        all_coins = response.json()
        start = (page - 1) * limit
        end = start + limit
        coins_data = all_coins[start:end]
        binance_cache[cache_key] = coins_data

    return templates.TemplateResponse("coins.html", {"request": request, "coins": coins_data, "user": user})


@app.get("/coin/{symbol}", response_class=HTMLResponse)
async def coin_detail(
    request: Request, 
    symbol: str, 
    user: User = Depends(get_current_user)
):
    """Optimized coin detail view with smaller graph data"""
    await rate_limiter(request)

    # Fetch basic coin details
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol.upper()}")
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Coin not found")
        coin = response.json()
        change_percent = float(coin.get("priceChangePercent", 0))
        trend = "up" if change_percent > 0 else "down" if change_percent < 0 else "stable"
        coin["trend"] = trend
    # Reduce graph data to improve performance
    async with httpx.AsyncClient() as client:
        current_time_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
        params = {
            "symbol": symbol.upper(),
            "interval": "1h",
            "endTime": current_time_ms,
            "limit": 50  # Fetch fewer data points
        }
        response = await client.get("https://api.binance.com/api/v3/klines", params=params)
        data = response.json()

    timestamps = [int(item[0]) for item in data]
    closing_prices = [float(item[4]) for item in data]
    dates = [datetime.datetime.fromtimestamp(ts / 1000).strftime("%H:%M") for ts in timestamps]

    graph_data = {
        "labels": dates,
        "prices": closing_prices
    }

    return templates.TemplateResponse("coin_detail.html", {
        "request": request,
        "coin": coin,
        "graph_data": graph_data,
        "user": user
    })


@app.get("/weather", response_class=HTMLResponse)
async def weather(
    request: Request, 
    user: User = Depends(get_current_user)
):
    """Cached weather endpoint (reduced API calls)"""
    await rate_limiter(request)

    if "weather" in weather_cache:
        weather_data = weather_cache["weather"]
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.data.gov.sg/v1/environment/air-temperature")
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Error fetching weather data")
            
            weather_data = response.json()
            weather_cache["weather"] = weather_data

    reading_dict = {reading["station_id"]: reading["value"] for reading in weather_data.get("items", [{}])[0].get("readings", [])}
    
    return templates.TemplateResponse("weather.html", {
        "request": request,
        "weather": weather_data,
        "reading_dict": reading_dict,
        "user": user
    })


@app.post("/edit-profile", response_class=HTMLResponse)
async def edit_profile(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    bio: str = Form(None),
    phone: str = Form(None),
    password: str = Form(None),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Optimized profile update with async file upload"""
    await rate_limiter(request)

    user.username = username
    user.email = email
    user.bio = bio
    user.phone = phone

    if password:
        user.hashed_password = auth.get_password_hash(password)

    if photo:
        upload_dir = "static/uploads/"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{photo.filename}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as f:
            f.write(await photo.read())

        user.image_url = f"/static/uploads/{filename}"

    db.commit()
    return RedirectResponse(url="/profile", status_code=status.HTTP_302_FOUND)

@app.get("/google")
async def login(request: Request):
    """Redirect user to Google's OAuth2 authorization page"""
    # Ensure the redirect URI matches the callback registered in the Google console
    redirect_uri = "http://localhost:8000/auth/google"  
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.api_route("/auth/google", methods=["GET", "POST"])
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """
    Callback endpoint after Google OAuth
    - Register new users
    - Authenticate existing users
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")  # Correctly fetch user info

        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        email = user_info["email"]
        name = user_info["name"]
        picture = user_info.get("picture")

        # Check if user exists in the database
        user = db.query(User).filter(User.email == email).first()

        if not user:
            # Create a new user if not registered
            new_user = User(
                username=name,
                email=email,
                image_url=picture,
                created_at=datetime.datetime.utcnow(),
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user

        # Generate access token
        access_token = auth.create_access_token({"user_id": user.id})

        # Store token in cookie
        response = RedirectResponse(url="/profile")
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="Lax")
        return response

    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")
# Facebook login route
# Facebook login route
@app.get("/facebook")
async def facebook_login(request: Request):
    """Redirects user to Facebook for authentication"""
    try:
        redirect_uri = request.url_for('facebook_callback')
        return await oauth.facebook.authorize_redirect(request, redirect_uri)
    except Exception as e:
        return HTMLResponse(f"<h3>Login failed: {str(e)}</h3>")

# Facebook callback route with error handling
@app.get("/facebook/callback")
async def facebook_callback(request: Request):
    """Handles the callback from Facebook"""
    try:
        # Retrieve access token
        token = await oauth.facebook.authorize_access_token(request)
        
        if not token:
            return RedirectResponse(url="/login?error=Facebook login failed: No token received")

        # Fetch user profile data with more fields
        user_info = await oauth.facebook.get(
            'https://graph.facebook.com/me?fields=id,name,email,picture,username', 
            token=token
        )
        
        if not user_info:
            return RedirectResponse(url="/login?error=Failed to fetch user info")

        user = user_info.json()

        # Extract user details
        name = user.get("name")  # Display name
        email = user.get("email")
        username = user.get("username", name)  # Use username if available, otherwise fallback to name
        picture = user.get("picture", {}).get("data", {}).get("url")

        # Display user info
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": {
                "username": username,
                "name": name,
                "email": email,
                "picture": picture
            }
        })

    except Exception as e:
        # Redirect to login page on error
        return RedirectResponse(url=f"/login?error=Facebook login failed: {str(e)}")
