from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def index():
    return {'data':{'name': 'Shobha'}}

@app.get("/about")
def about():
    return {'data':{'Profession: Software Engineer with passionate Teacher and great leader be the same.'}}


