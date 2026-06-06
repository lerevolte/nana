import aiomysql
import os
import logging
from fastapi import FastAPI, Query, HTTPException
from contextlib import asynccontextmanager
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ MySQL ===
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "nanobanana_db")
DB_PORT = int(os.getenv("MYSQL_PORT", 3306))

# Часовой пояс сервера MySQL и целевой (Москва)
TZ_SERVER = "America/New_York"
TZ_TARGET = "Europe/Moscow"

def to_msk(col):
    """Конвертирует колонку из серверного TZ в московский"""
    return f"CONVERT_TZ({col}, '{TZ_SERVER}', '{TZ_TARGET}')"

pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    try:
        pool = await aiomysql.create_pool(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
            db=DB_NAME, cursorclass=aiomysql.DictCursor, autocommit=True
        )
        yield
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

app = FastAPI(title="NanoBanana Analytics Pro", lifespan=lifespan)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_date_filter(start_date: str = None, end_date: str = None, col="created_at", alias=""):
    """Фильтр по дате с конвертацией в московское время"""
    conds = []
    params = []
    prefix = f"{alias}." if alias else ""
    msk_col = to_msk(f"{prefix}{col}")
    
    if start_date:
        conds.append(f"{msk_col} >= %s")
        params.append(start_date)
    if end_date:
        if len(end_date) == 10: end_date += " 23:59:59"
        conds.append(f"{msk_col} <= %s")
        params.append(end_date)
    return " AND ".join(conds), params

def get_source_filter(sources: str = None, col="utm_source", alias=""):
    if not sources or sources == 'ALL':
        return "", []
    
    source_list = sources.split(',')
    placeholders = ','.join(['%s'] * len(source_list))
    prefix = f"{alias}." if alias else ""
    return f"{prefix}{col} IN ({placeholders})", source_list

async def check_pool():
    if not pool: raise HTTPException(500, "DB Pool not initialized")

# === ЭНДПОИНТЫ API ===

@app.get("/analytics/kpi_filtered")
async def get_kpi(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "u")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            where = "WHERE 1=1"
            if d_where: where += f" AND {d_where}"
            if s_where: where += f" AND {s_where}"
            params = d_params + s_params

            sql_users = f"SELECT COUNT(*) as total, SUM(is_blocked) as blocked FROM users u {where}"
            await cur.execute(sql_users, tuple(params))
            u_res = await cur.fetchone()
            
            pd_where, pd_params = get_date_filter(start_date, end_date, "created_at", "p")
            
            sql_pay = f"""
                SELECT SUM(p.amount) as rev, COUNT(p.id) as orders, COUNT(DISTINCT p.user_id) as payers
                FROM payments p
                JOIN users u ON u.id = p.user_id
                WHERE p.status = 'succeeded'
            """
            if pd_where: sql_pay += f" AND {pd_where}"
            if s_where: sql_pay += f" AND {s_where}"
            
            pay_params = pd_params + s_params
            await cur.execute(sql_pay, tuple(pay_params))
            p_res = await cur.fetchone()

            rev = float(p_res['rev'] or 0)
            payers = p_res['payers'] or 0
            
            return {
                "revenue": rev,
                "new_users": u_res['total'],
                "orders_count": p_res['orders'],
                "payers": payers,
                "blocked_users": int(u_res['blocked'] or 0),
                "arppu": round(rev / payers) if payers > 0 else 0
            }

@app.get("/analytics/dynamics_daily")
async def dynamics_daily(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "p")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            sql = f"""
                SELECT DATE_FORMAT({to_msk('p.created_at')}, '%%Y-%%m-%%d') as date_point, SUM(p.amount) as revenue
                FROM payments p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE p.status = 'succeeded'
                {f'AND {d_where}' if d_where else ''}
                {f'AND {s_where}' if s_where else ''}
                GROUP BY 1 ORDER BY 1
            """
            await cur.execute(sql, tuple(d_params + s_params))
            return await cur.fetchall()

@app.get("/analytics/dynamics_subscribers")
async def dynamics_subs(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "u")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            sql = f"""
                SELECT DATE_FORMAT({to_msk('u.created_at')}, '%%Y-%%m-%%d') as date_point, COUNT(*) as users_count
                FROM users u
                WHERE 1=1
                {f'AND {d_where}' if d_where else ''}
                {f'AND {s_where}' if s_where else ''}
                GROUP BY 1 ORDER BY 1
            """
            await cur.execute(sql, tuple(d_params + s_params))
            return await cur.fetchall()

@app.get("/analytics/dynamics_hourly")
async def dynamics_hourly(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "p")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            sql = f"""
                SELECT DATE_FORMAT({to_msk('p.created_at')}, '%%H:00') as hour_point, SUM(p.amount) as revenue
                FROM payments p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE p.status = 'succeeded'
                {f'AND {d_where}' if d_where else ''}
                {f'AND {s_where}' if s_where else ''}
                GROUP BY 1 ORDER BY 1
            """
            await cur.execute(sql, tuple(d_params + s_params))
            return await cur.fetchall()

@app.get("/analytics/dynamics_repeats")
async def dynamics_repeats(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "p")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            sql = f"""
                SELECT DATE_FORMAT({to_msk('p.created_at')}, '%%Y-%%m-%%d') as date_point, 
                       SUM(p.amount) as revenue,
                       COUNT(p.id) as orders
                FROM payments p
                JOIN users u ON u.id = p.user_id
                JOIN (
                    SELECT user_id, MIN(created_at) as first_pay 
                    FROM payments 
                    WHERE status='succeeded' 
                    GROUP BY user_id
                ) fp ON p.user_id = fp.user_id
                WHERE p.status = 'succeeded'
                AND p.created_at > fp.first_pay
                {f'AND {d_where}' if d_where else ''}
                {f'AND {s_where}' if s_where else ''}
                GROUP BY date_point ORDER BY date_point ASC
            """
            await cur.execute(sql, tuple(d_params + s_params))
            rows = await cur.fetchall()
            
            result = []
            for r in rows:
                result.append({
                    "date_point": r['date_point'],
                    "revenue": float(r['revenue']) if r['revenue'] else 0,
                    "orders": int(r['orders'])
                })
            return result

@app.get("/analytics/funnel")
async def get_funnel(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "u")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            where = "WHERE 1=1"
            if d_where: where += f" AND {d_where}"
            if s_where: where += f" AND {s_where}"
            params = d_params + s_params

            await cur.execute(f"SELECT COUNT(*) as cnt FROM users u {where}", tuple(params))
            res_vis = await cur.fetchone()
            
            pd_where, pd_params = get_date_filter(start_date, end_date, "created_at", "p")
            sql_paid = f"""
                SELECT COUNT(DISTINCT p.user_id) as cnt 
                FROM payments p 
                JOIN users u ON u.id = p.user_id
                WHERE p.status='succeeded' 
                {f'AND {pd_where}' if pd_where else ''}
                {f'AND {s_where}' if s_where else ''}
            """
            await cur.execute(sql_paid, tuple(pd_params + s_params))
            res_paid = await cur.fetchone()
            
            return {
                "visitors": res_vis['cnt'],
                "generated_text": int(res_vis['cnt'] * 0.4),
                "paid": res_paid['cnt']
            }

@app.get("/analytics/retention")
async def get_retention(start_date: str = None, end_date: str = None, sources: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "p")
            s_where, s_params = get_source_filter(sources, "utm_source", "u")
            
            sql = f"""
                SELECT p.user_id, p.amount, p.created_at
                FROM payments p
                JOIN users u ON u.id = p.user_id
                WHERE p.status = 'succeeded'
                {f'AND {d_where}' if d_where else ''}
                {f'AND {s_where}' if s_where else ''}
            """
            await cur.execute(sql, tuple(d_params + s_params))
            payments = await cur.fetchall()
            
            if not payments:
                return {"new_revenue": 0, "repeat_revenue": 0, "repeat_share": 0}
            
            uids = list(set(p['user_id'] for p in payments))
            placeholders = ','.join(['%s'] * len(uids))
            
            sql_first = f"""
                SELECT user_id, MIN(created_at) as first_pay 
                FROM payments 
                WHERE status='succeeded' AND user_id IN ({placeholders}) 
                GROUP BY user_id
            """
            await cur.execute(sql_first, tuple(uids))
            first_dates = {r['user_id']: str(r['first_pay']) for r in await cur.fetchall()}
            
            new_rev = 0
            rep_rev = 0
            
            for p in payments:
                f_date = first_dates.get(p['user_id'])
                p_date = str(p['created_at'])
                amt = float(p['amount'])
                
                if f_date and p_date > f_date:
                     rep_rev += amt
                else:
                     new_rev += amt
            
            total = new_rev + rep_rev
            return {
                "new_revenue": new_rev,
                "repeat_revenue": rep_rev,
                "repeat_share": round(rep_rev/total*100, 1) if total else 0
            }

@app.get("/analytics/sources_detailed")
async def get_sources_detailed(start_date: str = None, end_date: str = None):
    await check_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            d_where, d_params = get_date_filter(start_date, end_date, "created_at", "u")
            pd_where, pd_params = get_date_filter(start_date, end_date, "created_at", "p")
            
            sql_u = f"""
                SELECT utm_source, COUNT(*) as users, SUM(is_blocked) as blocked
                FROM users u
                WHERE 1=1 {f'AND {d_where}' if d_where else ''}
                GROUP BY utm_source
            """
            await cur.execute(sql_u, tuple(d_params))
            u_data = {r.get('utm_source'): r for r in await cur.fetchall()} 
            
            sql_p = f"""
                SELECT u.utm_source as utm_source, 
                       COUNT(DISTINCT p.user_id) as payers,
                       SUM(p.amount) as rev,
                       COUNT(p.id) as trans_count
                FROM payments p
                JOIN users u ON u.id = p.user_id
                WHERE p.status='succeeded'
                {f'AND {pd_where}' if pd_where else ''}
                GROUP BY u.utm_source
            """
            await cur.execute(sql_p, tuple(pd_params))
            p_data = {r['utm_source']: r for r in await cur.fetchall()}
            
            result = []
            all_sources = set(list(u_data.keys()) + list(p_data.keys()))
            
            for src in all_sources:
                u = u_data.get(src, {'users': 0, 'blocked': 0})
                p = p_data.get(src, {'payers': 0, 'rev': 0, 'trans_count': 0})
                
                vis = u['users']
                pay = p['payers']
                rev = float(p['rev'] or 0)
                
                result.append({
                    "source": src if src else "Direct",
                    "visitors": vis,
                    "leads": int(vis * 0.5),
                    "cr_lead": 50,
                    "payers": pay,
                    "cr_sale": round(pay/vis*100, 1) if vis else 0,
                    "blocked_count": int(u['blocked'] or 0),
                    "repeat_trans": max(0, p['trans_count'] - pay),
                    "repeat_revenue": 0,
                    "repeat_share": 0,
                    "arppu": round(rev/pay) if pay else 0,
                    "revenue": rev
                })
                
            result.sort(key=lambda x: x['revenue'], reverse=True)
            return result

@app.get("/analytics/user_segments_detailed")
async def user_segments():
    return {
        "drafts": {"3-7": 10, "7-14": 5, "14-30": 2, "30+": 1},
        "inactive": {"3-7": 50, "7-14": 30, "14-30": 20, "30+": 100},
        "churn": {"3-7": 5, "7-14": 2, "14-30": 1, "30+": 0}
    }