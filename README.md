# Week 4 - Builder's Brain API

this is my week 4 submission for resolution (hack club python pathway). its an idea and resource management api built with fastapi and sqlite.

---

## what is this

basically i always have too many project ideas floating around and i also save a lot of tutorials and links but they're all over the place. this api fixes that. you dump your ideas, you dump your resources (links/tutorials/tools), tag both of them, and they automatically connect through tags.

so if i have a CAD project idea and i also saved a fusion 360 tutorial, both tagged `cad` — hitting `/explore/cad` shows me both together.

---

## features

## 🔑 api key auth
you register with your name and get a unique api key. every request needs that key. no key = rejected.

## 💡 idea tracking
add project ideas with a title, description, tag, and feasibility score (1-5). track their status from `raw` → `in-progress` → `done` or `abandoned`.

## 🔗 resource saving
save links, tutorials, docs, tools. tag them so they connect to your ideas automatically. mark them as useful after trying them.

## 🗺️ explore by tag
the main feature. hit `/explore/cad` and see all your cad ideas + cad resources in one place. everything connected through tags.

## 📊 personal stats
see how many ideas you've actually finished vs abandoned. how many resources you've saved and marked as useful.

## 🚦 rate limiting
post routes are limited to 5 requests per minute per api key to prevent abuse.

## 📝 activity logging
every time you add an idea or resource, it gets logged to a file in the background after the response is sent.

---

## valid tags
`cad` `python` `electronics` `hackclub` `robotics` `web` `general`

## valid resource types
`video` `article` `doc` `tool`

## valid idea statuses
`raw` `in-progress` `done` `abandoned`

---

## how to run

```bash
git clone <your-repo-url>
cd reso4
python3 -m venv .venv
source .venv/bin/activate
pip install "fastapi[standard]" slowapi
fastapi dev src/reso4/main.py
```

then go to `http://127.0.0.1:8000/docs`

---

## routes

| method | route | auth | what it does |
|--------|-------|------|--------------|
| POST | `/register` | ❌ | register and get api key |
| POST | `/ideas` | ✅ | add an idea |
| GET | `/ideas` | ✅ | get all ideas (filter by tag/status) |
| GET | `/ideas/{id}` | ✅ | get one idea + related resources |
| PATCH | `/ideas/{id}/status` | ✅ | update idea status |
| DELETE | `/ideas/{id}` | ✅ | delete an idea |
| POST | `/resources` | ✅ | add a resource |
| GET | `/resources` | ✅ | get all resources (filter by tag/type) |
| PATCH | `/resources/{id}/useful` | ✅ | mark resource as useful |
| DELETE | `/resources/{id}` | ✅ | delete a resource |
| GET | `/explore/{tag}` | ✅ | see ideas + resources by tag |
| GET | `/stats` | ✅ | your personal stats |

---

## screenshot

(working.png)

---

made by Suvam Pathak - A Hack Club Member
