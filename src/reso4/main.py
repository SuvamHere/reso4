from fastapi import FASTAPI, HTTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
import sqlite3
import secrets
import secrets
import datetime
import os

def get_api_key_from_header(request:Request) -> str:
    return request.headers.get("x-api-key","unknown")

limiter = Limiter(key_func=get_api_key_from_header)
app = FASTAPI()
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )
#For constants
DB_FILE = "brain.db"
LOG_FILE = "activity.log" 
VALID_TAG = ["CAD","Python","Electronics","HackClub","Robotics","web","General"] 
VALID_TYPES = ["Video","Article","Doc","Tool"]
VALID_STATUSES = ["Raw","In-Progress","Done","Abandoned"]

#For database setup
def get_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    return conn, cursor

def init_db():
    conn, cursor = get_db()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            link TEXT NOT NULL,
            tags TEXT,
            type TEXT,
            status TEXT,
            submitter TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            tag TEXT NOT NULL,
            feasibility INTEGER DEFAULT 3,
            status TEXT DEFAULT 'raw',
            created_date TEXT NOT NULL
            )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            tag TEXT NOT NULL,
            type TEXT NOT NULL,
            useful INTEGER DEFAULT 0,
            created_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    
init_db()

#Auth is here 
async def verify_api_key(x_api_key: str = Header()):
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM users WHERE api_key = ?", (x_api_key,))
    user = cursor.fetchone()
    conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

#Background task for logging is here
def log_activity(action: str, detail: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now()} | {action} | {detail}\n")

#For models
class RegisterBody(BaseModel):
    name: str
class IdeaBody(BaseModel):
    title: str
    description: str | None = None
    tag: str = "General"
    feasibility: int = 3

class StatusBody(BaseModel):
    status: str

class ResourceBody(BaseModel):
    title: str
    url: str
    tag: str = "General"
    type: str = "Article"
    
# For Routes
#Resiter and getting API key part is here
@app.post("/register")
async def register(body: RegisterBody):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    conn, cursor = get_db()
    api_key = secrets.token_hex(16)
    cursor.execute(
        "INSERT INTO users (name, api_key, created_date) VALUES (?, ?, ?)",
        (body.name, api_key, str(datetime.date.today()))
    )
    conn.commit()
    conn.close()
    return {
        "message": "Registered!DOn't Forget to save your API key, you won't see it again.",
        "name": body.name,
        "api_key": api_key
    }
#adding idea route is here
@app.post("/ideas")
@limiter.limit("5/minute")
async def add_idea(
    request: Request,
    body: IdeaBody,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    if not body.title.strip():
        raise HTTTPException(status_code=400, detail="Title cannot be empty")
    if body.tag not in VALID_TAG:
        raise HTTTPException(status_code=400, detail=f"Invalid tag. Valid tags are: {', '.join(VALID_TAG)}")
    if body.feasibility < 1 or body.feasibility > 5:
            raise HTTPException(status_code=400, detail="Feasibility must be between 1 and 5")
    conn, cursor = get_db()
    cursor.execute(
        "INSERT INTO ideas (user_key, title, description, tag, feasibility, status, created_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (api_key, body.title, body.description, body.tag, body.feasibility, "raw", str(datetime.date.today()))
    )
    conn.commit()
    idea_id = cursor.lastrowid
    conn.close()
    background_tasks.add_task(log_activity, "ADD_IDEA", f"id={idea_id} title={body.title} tag={body.tag}")
    return{
        "id": idea_id,
        "title": body.title,
        "description": body.description,
        "tag": body.tag,
        "feasibility": body.feasibility,
        "status": "raw",
        "created_date": str(datetime.date.today())
    }
#getting all the ideas route is here
@app.get("/ideas")
@limiter.limit("10/minute")
async def get_ideas(
    tag: str | None = None,
    status: str | None = None,
    api_key: str = Depends(verify_api_key)
):
    conn, cursor = get_db()
    query = "SELECT * FROM ideas WHERE user_key = ?"
    params = [api_key]
    if tag is not None:
        query += " AND tag = ?"
        params.append(tag)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[2], "description": r[3], "tag": r[4], "feasibility": r[5], "status": r[6], "created_date": r[7]} for r in rows]
# getting single idea route is here + related resources by tag 
@app.get("/ideas/{idea_id}")
async def get_idea(idea_id: int, api_key: str = Depends(verify_api_key)):
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM ideas WHERE id = ? AND user_key = ?", (idea_id, api_key))
    idea = cursor.fetchone()
    if idea is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Idea not found")
    cursor.execute("SELECT * FROM resources WHERE tag = ? AND user_key = ?", (idea[4], api_key))
    resources = cursor.fetchall()
    conn.close()
    return {
        "idea": {"id": idea[0], "title": idea[2], "description": idea[3], "tag": idea[4], "feasibility": idea[5], "status": idea[6], "created_date": idea[7]},
        "related_resources": [{"id": r[0], "title": r[2], "url": r[3], "tag": r[4], "type": r[5], "useful": bool(r[6])} for r in resources]
    }
#updating idea status route is here
@app.patch("/ideas/{idea_id}/status")
async def update_status(idea_id: int, body: StatusBody, api_key: str = Depends(verify_api_key)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {VALID_STATUSES}")
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM ideas WHERE id = ? AND user_key = ?", (idea_id, api_key))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Idea not found")
    cursor.execute("UPDATE ideas SET status = ? WHERE id = ?", (body.status, idea_id))
    conn.commit()
    conn.close()
    return {"message": f"Status updated to {body.status}"}

#deleting idea route is here
@app.delete("/ideas/{idea_id}")
async def delete_idea(idea_id: int, api_key: str = Depends(verify_api_key)):
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM ideas WHERE id = ? AND user_key = ?", (idea_id, api_key))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Idea not found")
    cursor.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    conn.commit()
    conn.close()
    return {"message": "Idea deleted successfully"}
#adding resource route is here
@app.post("/resources")
@limiter.limit("5/minute")
async def add_resource(
    request: Request,
    body: ResourceBody,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if not body.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    if body.tag not in VALID_TAG:
        raise HTTPException(status_code=400, detail=f"Invalid tag. Valid tags are: {', '.join(VALID_TAG)}")
    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid types are: {', '.join(VALID_TYPES)}")
    conn, cursor = get_db()
    cursor.execute(
        "INSERT INTO resources (user_key, title, url, tag, type, useful, created_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (api_key, body.title, body.url, body.tag, body.type, 0, str(datetime.date.today()))
    )
    conn.commit()
    resource_id = cursor.lastrowid
    conn.close()
    background_tasks.add_task(log_activity, "ADD_RESOURCE", f"id={resource_id} title={body.title} tag={body.tag} type={body.type}")
    return {
        "id": resource_id,
        "title": body.title,
        "url": body.url,
        "tag": body.tag,
        "type": body.type,
        "useful": False,
        "created_date": str(datetime.date.today())
    }
    
#getting all the resources route is here
@app.get("/resources")
async def get_resources(
    tag: str | None = None,
    type: str | None = None,
    api_key: str = Depends(verify_api_key)
):
    conn, cursor = get_db()
    query = "SELECT * FROM resources WHERE user_key = ?"
    params = [api_key]
    if tag is not None:
        query += " AND tag = ?"
        params.append(tag)
    if type is not None:
        query += " AND type = ?"
        params.append(type)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[2], "url": r[3], "tag": r[4], "type": r[5], "useful": bool(r[6]), "created_date": r[7]} for r in rows]

#marking resources as useful route is here
@app.patch("/resources/{resource_id}/useful")
async def mark_useful(resource_id: int, api_key: str = Depends(verify_api_key)):
    conn,cursor = get_db()
    cursor.execute("SELECT * FROM resources WHERE id = ? AND user_key = ?", (resource_id, api_key))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Resource not found")
    cursor.execute("UPDATE resources SET useful = 1 WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()
    return{"Message": "Resource marked as useful!"}

#deleting resource route is here
@app.delete("/resources/{resource_id}")
async def delete_resource(resoruce_id: int, api_key: str = Depends(verify_api_key)):
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM resources WHERE id = ? AND user_key = ?", (resource_id, api_key))
    if cursor.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Resource not found")
    cursor.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()
    return{"message": "Resource deleted successfully"}

#Exploring by tags route is here- ideas+ resources together
@app.get("/explore/{tag}")
async def explore_tag(tag: str, api_key: str = Depends(verify_api_key)):
    if tag not in VALID_TAG:
        raise HTTTPException(status_code=400, detail=f"Invalid tag. Choose from: {VALID_TAGS}")
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM ideas WHERE tag = ? AND user_key = ?", (tag, api_key))
    ideas = cursor.fetchall()
    cursor.execute("SELECT * FROM resources WHERE tag = ? AND user_key = ?", (tag, api_key))
    resources = cursor.fetchall()
    conn.close()
    return {
        "tag": tag,
        "ideas": [{"id": i[0], "title": i[2], "description": i[3], "feasibility": i[5], "status": i[6]} for i in ideas],
        "resources": [{"id": r[0], "title": r[2], "url": r[3], "type": r[5], "useful": bool(r[6])} for r in resources]
    }
#personal stats route is here
@app.get("/stats")
async def get_stats(api_key: str = Depends(verify_api_key)):
    conn, Cursor = get_db()
    cursor.execute("SELECT COUNT(*) FROM ideas WHERE user_key = ?", (api_key,))
    total_ideas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ideas WHERE user_key = ? AND status = 'done'", (api_key,))
    done_ideas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ideas WHERE user_key = ? AND status = 'abandoned'", (api_key,))
    abandoned_ideas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resources WHERE user_key = ?", (api_key,))
    total_resources = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM resources WHERE user_key = ? AND useful = 1", (api_key,))
    useful_resources = cursor.fetchone()[0]
    conn.close()
    return {
        "ideas": {
            "total": total_ideas,
            "done": done_ideas,
            "abandoned": abandoned_ideas,
            "in_progress": total_ideas - done_ideas - abandoned_ideas
        },
        "resources": {
            "total": total_resources,
            "marked_useful": useful_resources
        }
    }

def main():
    import uvicorn
    uvicorn.run("reso4.main:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()