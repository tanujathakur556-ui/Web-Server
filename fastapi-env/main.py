from fastapi import FastAPI

from typing import Optional

from pydantic import BaseModel

app = FastAPI()

@app.get("/blog")
def index(limit=10, published:bool=True, sort:Optional[str]=None):
    if published:
        return {'data': f"{limit} published blogs from the db"}
    
    else:
        return {'data':f'{limit} blogs from db'}


@app.get('/blog/unpublished')
def unpublished():
    return {'data': 'All unpublished blogs'}


@app.get('/blog/{id}')
def show(id: int):
    #fetch blog with id = id
    return {'data': id}


@app.get('/blog/{id}/comments')
def comments(id, limit=10):
    #fetch comments of blog with id = id
    return {'data': {'1','2'}}

@app.get("/about")
def about():
    return {'data':{'Profession: Software Engineer with passionate Teacher and great leader be the same. '}}
class Blog(BaseModel):
    
    title: str
    body: str
    published: Optional[bool]



@app.post('/blog')
def create_blog(request: Blog):
    
    return {'data': f"Blog is created with title as {request.title}"}