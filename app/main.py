from __future__ import annotations

import logging
import traceback
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import BASE_DIR, CORS_ORIGINS, SESSION_COOKIE_NAME, SESSION_DAYS, SESSION_HTTPS_ONLY
from .db import SessionLocal, get_db, init_db
from .models import Card, User
from .routers.cards import router as cards_router
from .routers.rewards import router as rewards_router
from .routers.statements import router as statements_router
from .services.admin import get_admin_dashboard
from .services.analysis import analyze_statement_rows
from .services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    current_user_from_request,
    ensure_default_admin,
    migrate_auth_schema_if_needed,
    revoke_token,
    set_user_password,
)
from .services.card_advisor import get_category_options, get_merchant_dropdown_options, suggest_cards_for_profile
from .services.dashboard import get_card_database_rows, get_dashboard_stats, run_cardpilot_self_check
from .services.portfolio import add_user_card, get_user_card_ids, list_user_cards, remove_user_card
from .services.reward_engine import recommend_best_cards
from .services.seed_data import ensure_professional_seed_data
from .services.statement_parser import parse_statement_file

logger = logging.getLogger(__name__)

APP_NAME = "CardPilot"
APP_VERSION = "1.6.0"

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cards_router)
app.include_router(rewards_router)
app.include_router(statements_router)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _set_login_cookie(response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=SESSION_HTTPS_ONLY,
        max_age=SESSION_DAYS * 24 * 60 * 60,
    )


def _clear_login_cookie(response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME)


def _current_user(request: Request, db: Session) -> User | None:
    return current_user_from_request(request, db)


def _redirect_login(next_url: str = "/app") -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)


def _app_context(request: Request, db: Session, user: User, **extra) -> dict:
    cards = db.query(Card).order_by(Card.bank_name, Card.card_name).limit(600).all()
    merchants = get_merchant_dropdown_options(db)
    categories = get_category_options()
    ctx = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "current_user": user,
        "cards": cards,
        "saved_cards": list_user_cards(db, user.user_id),
        "merchants": merchants,
        "categories": categories,
        "stats": get_dashboard_stats(db, user.user_id),
        "active_page": "app",
    }
    ctx.update(extra)
    return ctx


def _base_context(request: Request, db: Session, **extra) -> dict:
    ctx = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "current_user": _current_user(request, db),
        "active_page": extra.pop("active_page", "home"),
    }
    ctx.update(extra)
    return ctx


@app.on_event("startup")
def on_startup():
    init_db()
    with SessionLocal() as db:
        cards_count = db.query(Card).count()
    if cards_count == 0:
        try:
            from scripts.import_workbook import import_workbook
            import_workbook()
        except Exception:
            logger.exception("Could not import seed workbook on startup")
    with SessionLocal() as db:
        migrate_auth_schema_if_needed(db)
        ensure_professional_seed_data(db)
        ensure_default_admin(db)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cardpilot", "version": APP_VERSION}


@app.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)):
    stats = get_dashboard_stats(db)
    return templates.TemplateResponse(request, "landing.html", _base_context(request, db, stats=stats, categories=get_category_options(), active_page="home"))


@app.get("/app", response_class=HTMLResponse)
def app_dashboard(request: Request, message: str | None = None, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app")
    return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, message=message))


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/app", db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user:
        return RedirectResponse(url=next or "/app", status_code=303)
    return templates.TemplateResponse(request, "auth.html", _base_context(request, db, mode="login", next=next, active_page="login"))


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, next: str = "/app", db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user:
        return RedirectResponse(url=next or "/app", status_code=303)
    return templates.TemplateResponse(request, "auth.html", _base_context(request, db, mode="signup", next=next, active_page="signup"))


@app.post("/auth/signup")
def auth_signup(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    preferred_reward_type: str = Form("cashback"),
    next: str = Form("/app"),
    db: Session = Depends(get_db),
):
    try:
        user = create_user(db, email=email, password=password, full_name=full_name, preferred_reward_type=preferred_reward_type, request=request)
        token = create_access_token(db, user, token_name="web-session")
        response = RedirectResponse(url=next or "/app", status_code=303)
        _set_login_cookie(response, token)
        return response
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth.html",
            _base_context(request, db, mode="signup", next=next, error=str(exc), active_page="signup"),
            status_code=400,
        )


@app.post("/auth/login")
def auth_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/app"),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, email=email, password=password, request=request)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth.html",
            _base_context(request, db, mode="login", next=next, error="Invalid email or password.", active_page="login"),
            status_code=401,
        )
    token = create_access_token(db, user, token_name="web-session")
    response = RedirectResponse(url=next or "/app", status_code=303)
    _set_login_cookie(response, token)
    return response


@app.post("/auth/logout")
def auth_logout(request: Request, db: Session = Depends(get_db)):
    revoke_token(db, request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse(url="/", status_code=303)
    _clear_login_cookie(response)
    return response


@app.get("/admin", response_class=HTMLResponse)
def admin_portal(request: Request, message: str | None = None, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/admin")
    if not user.is_admin:
        return templates.TemplateResponse(request, "forbidden.html", _base_context(request, db, active_page="admin", error="Admin access required."), status_code=403)
    return templates.TemplateResponse(
        request,
        "admin.html",
        _base_context(request, db, active_page="admin", admin_stats=get_admin_dashboard(db), message=message),
    )


@app.post("/admin/users/reset-password", response_class=HTMLResponse)
def admin_reset_user_password(
    request: Request,
    user_id: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin_user = _current_user(request, db)
    if not admin_user:
        return _redirect_login("/admin")
    if not admin_user.is_admin:
        return templates.TemplateResponse(
            request,
            "forbidden.html",
            _base_context(request, db, active_page="admin", error="Admin access required."),
            status_code=403,
        )
    target = db.get(User, user_id)
    if not target:
        return templates.TemplateResponse(
            request,
            "admin.html",
            _base_context(request, db, active_page="admin", admin_stats=get_admin_dashboard(db), error="User not found."),
            status_code=404,
        )
    try:
        set_user_password(db, user=target, new_password=new_password, changed_by_user_id=admin_user.user_id, request=request)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin.html",
            _base_context(request, db, active_page="admin", admin_stats=get_admin_dashboard(db), error=str(exc)),
            status_code=400,
        )
    return RedirectResponse(url=f"/admin?message={quote('Password reset for ' + (target.email or target.user_id))}#users", status_code=303)


@app.get("/database", response_class=HTMLResponse)
def database_view(request: Request, q: str | None = Query(None), db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/database")
    rows = get_card_database_rows(db, q=q, limit=250)
    return templates.TemplateResponse(
        request,
        "database.html",
        _base_context(request, db, active_page="database", stats=get_dashboard_stats(db), q=q or "", rows=rows),
    )


@app.get("/self-test", response_class=HTMLResponse)
def self_test(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/self-test")
    report = run_cardpilot_self_check(db)
    return templates.TemplateResponse(
        request,
        "self_test.html",
        _base_context(request, db, active_page="self-test", report=report, stats=get_dashboard_stats(db)),
    )


@app.get("/self-test.json")
def self_test_json(db: Session = Depends(get_db)):
    return run_cardpilot_self_check(db)


@app.post("/ui/my-cards/add", response_class=HTMLResponse)
def ui_add_card(request: Request, card_id: str = Form(...), masked_last4: str | None = Form(None), db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app#my-cards")
    try:
        add_user_card(db, user_id=user.user_id, card_id=card_id, masked_last4=masked_last4)
        card = db.get(Card, card_id)
        message = f"Saved card: {card.bank_name} - {card.card_name}" if card else "Saved card."
        return RedirectResponse(url=f"/app?message={quote(message)}#my-cards", status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, error=str(exc)), status_code=400)


@app.post("/ui/my-cards/remove", response_class=HTMLResponse)
def ui_remove_card(request: Request, user_card_id: str = Form(...), db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app#my-cards")
    try:
        remove_user_card(db, user_id=user.user_id, user_card_id=user_card_id)
        return RedirectResponse(url="/app?message=Saved%20card%20removed#my-cards", status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, error=str(exc)), status_code=400)


@app.post("/ui/recommend", response_class=HTMLResponse)
def ui_recommend(
    request: Request,
    merchant_raw: str = Form(...),
    merchant_custom: str | None = Form(None),
    amount_inr: float = Form(...),
    category: str | None = Form(None),
    use_my_cards_only: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app#best-card")
    try:
        merchant_value = merchant_custom.strip() if merchant_custom and merchant_custom.strip() else merchant_raw
        card_ids = get_user_card_ids(db, user.user_id) if use_my_cards_only else None
        if use_my_cards_only and not card_ids:
            raise ValueError("Add at least one card in My Cards before using My Cards-only recommendations.")
        recommendations = recommend_best_cards(
            db=db,
            merchant_raw=merchant_value,
            amount_inr=amount_inr,
            category=category or None,
            top_n=10,
            card_ids=card_ids,
        )
        result = {
            "merchant_raw": merchant_value,
            "amount_inr": amount_inr,
            "category": category,
            "scope": "My saved cards" if use_my_cards_only else "All database cards",
            "recommendations": recommendations,
        }
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, recommendation_result=result))
    except ValueError as exc:
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, error=str(exc)), status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error while recommending cards")
        return templates.TemplateResponse(
            request,
            "app.html",
            _app_context(request, db, user, error=f"Unexpected recommendation error: {exc}", debug_detail=traceback.format_exc()),
            status_code=500,
        )


@app.post("/ui/card-advisor", response_class=HTMLResponse)
def ui_card_advisor(
    request: Request,
    monthly_spend_inr: float = Form(...),
    primary_category: str = Form(...),
    secondary_category: str | None = Form(None),
    reward_preference: str = Form("cashback"),
    annual_fee_preference: str = Form("low_fee"),
    travel_frequency: str = Form("sometimes"),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app#adviser")
    try:
        suggestion_result = suggest_cards_for_profile(
            db=db,
            monthly_spend_inr=monthly_spend_inr,
            primary_category=primary_category,
            secondary_category=secondary_category or None,
            reward_preference=reward_preference,
            annual_fee_preference=annual_fee_preference,
            travel_frequency=travel_frequency,
            top_n=8,
        )
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, suggestion_result=suggestion_result))
    except ValueError as exc:
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, error=str(exc)), status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error while suggesting cards")
        return templates.TemplateResponse(
            request,
            "app.html",
            _app_context(request, db, user, error=f"Unexpected card suggestion error: {exc}", debug_detail=traceback.format_exc()),
            status_code=500,
        )


@app.post("/ui/analyze", response_class=HTMLResponse)
async def ui_analyze(
    request: Request,
    card_id: str = Form(...),
    statement_password: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if not user:
        return _redirect_login("/app#analyze")
    content = await file.read()
    try:
        rows = parse_statement_file(file.filename or "statement.csv", content, password=statement_password)
        if not rows:
            raise ValueError("No valid transactions found in uploaded file. Check that your file has merchant and amount columns.")
        result = analyze_statement_rows(db, card_id=card_id, rows=rows, source_name=file.filename or "upload", file_content=content, user_id=user.user_id)
        card = db.get(Card, card_id)
        return templates.TemplateResponse(
            request,
            "results.html",
            _base_context(request, db, active_page="analyze", result=result, card=card, stats=get_dashboard_stats(db)),
        )
    except ValueError as exc:
        return templates.TemplateResponse(request, "app.html", _app_context(request, db, user, error=str(exc)), status_code=400)
    except Exception as exc:
        logger.exception("Unexpected error while analyzing statement")
        return templates.TemplateResponse(
            request,
            "app.html",
            _app_context(request, db, user, error=f"Unexpected app error: {exc}", debug_detail=traceback.format_exc()),
            status_code=500,
        )


# Mobile/API auth endpoints. These return bearer tokens that the included mobile app can store and send.
@app.post("/api/auth/signup")
async def api_signup(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    try:
        user = create_user(
            db,
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            full_name=payload.get("full_name"),
            preferred_reward_type=payload.get("preferred_reward_type", "cashback"),
            request=request,
        )
        token = create_access_token(db, user, token_name="mobile-app")
        return {"access_token": token, "token_type": "bearer", "user": {"user_id": user.user_id, "email": user.email, "full_name": user.full_name, "is_admin": bool(user.is_admin)}}
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.post("/api/auth/login")
async def api_login(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    user = authenticate_user(db, email=payload.get("email", ""), password=payload.get("password", ""), request=request)
    if not user:
        return JSONResponse({"detail": "Invalid email or password."}, status_code=401)
    token = create_access_token(db, user, token_name="mobile-app")
    return {"access_token": token, "token_type": "bearer", "user": {"user_id": user.user_id, "email": user.email, "full_name": user.full_name, "is_admin": bool(user.is_admin)}}


@app.get("/api/me")
def api_me(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    return {"user_id": user.user_id, "email": user.email, "full_name": user.full_name, "is_admin": bool(user.is_admin), "preferred_reward_type": user.preferred_reward_type}


@app.get("/api/my-cards")
def api_my_cards(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    return {"cards": list_user_cards(db, user.user_id)}


@app.post("/api/my-cards")
async def api_add_card(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    payload = await request.json()
    try:
        card = add_user_card(db, user.user_id, payload.get("card_id", ""), payload.get("masked_last4"))
        return {"saved": True, "user_card_id": card.user_card_id}
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/api/admin/stats")
def api_admin_stats(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    if not user.is_admin:
        return JSONResponse({"detail": "Admin access required."}, status_code=403)
    return get_admin_dashboard(db)


@app.post("/public/card-advisor", response_class=HTMLResponse)
def public_card_advisor(
    request: Request,
    monthly_spend_inr: float = Form(...),
    primary_category: str = Form(...),
    secondary_category: str | None = Form(None),
    reward_preference: str = Form("cashback"),
    annual_fee_preference: str = Form("low_fee"),
    travel_frequency: str = Form("sometimes"),
    db: Session = Depends(get_db),
):
    try:
        suggestion_result = suggest_cards_for_profile(
            db=db,
            monthly_spend_inr=monthly_spend_inr,
            primary_category=primary_category,
            secondary_category=secondary_category or None,
            reward_preference=reward_preference,
            annual_fee_preference=annual_fee_preference,
            travel_frequency=travel_frequency,
            top_n=6,
        )
        return templates.TemplateResponse(
            request,
            "landing.html",
            _base_context(request, db, stats=get_dashboard_stats(db), categories=get_category_options(), suggestion_result=suggestion_result, active_page="home"),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "landing.html",
            _base_context(request, db, stats=get_dashboard_stats(db), categories=get_category_options(), error=str(exc), active_page="home"),
            status_code=400,
        )


@app.get("/api/cards")
def api_cards(q: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    query = db.query(Card)
    if q:
        pattern = f"%{q}%"
        query = query.filter((Card.card_name.ilike(pattern)) | (Card.bank_name.ilike(pattern)) | (Card.card_id.ilike(pattern)))
    rows = query.order_by(Card.bank_name, Card.card_name).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "card_id": row.card_id,
            "bank_name": row.bank_name,
            "card_name": row.card_name,
            "annual_fee": row.annual_fee,
            "reward_currency": row.reward_currency,
            "data_quality": row.mvp_data_quality,
        }
        for row in rows
    ]


@app.post("/api/recommend")
async def api_recommend(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    payload = await request.json()
    use_my_cards_only = bool(payload.get("use_my_cards_only", True))
    card_ids = get_user_card_ids(db, user.user_id) if use_my_cards_only else None
    if use_my_cards_only and not card_ids:
        return JSONResponse({"detail": "Add at least one card before using My Cards only recommendations."}, status_code=400)
    try:
        recommendations = recommend_best_cards(
            db=db,
            merchant_raw=payload.get("merchant_raw", ""),
            amount_inr=float(payload.get("amount_inr", 0)),
            category=payload.get("category") or None,
            top_n=int(payload.get("top_n", 5)),
            card_ids=card_ids,
        )
        return {"recommendations": recommendations}
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.post("/api/advisor")
async def api_card_advisor(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if not user:
        return JSONResponse({"detail": "Login required."}, status_code=401)
    payload = await request.json()
    try:
        return suggest_cards_for_profile(
            db=db,
            monthly_spend_inr=float(payload.get("monthly_spend_inr", 50000)),
            primary_category=payload.get("primary_category", "online shopping"),
            secondary_category=payload.get("secondary_category") or None,
            reward_preference=payload.get("reward_preference", "cashback"),
            annual_fee_preference=payload.get("annual_fee_preference", "low_fee"),
            travel_frequency=payload.get("travel_frequency", "sometimes"),
            top_n=int(payload.get("top_n", 8)),
        )
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
