from celery import Celery
from flavor import FlavorsManager

app = Celery('flavor_api', backend='redis://localhost:6379/0', broker = 'redis://localhost:6379/0')

handler = FlavorsManager()

@app.task
def post(message):
    print(message)
    return handler.create(message)

@app.task
def patch(message):
    print(message)
    return handler.update(message)

@app.task
def delete(message):
    return handler.delete(message)
