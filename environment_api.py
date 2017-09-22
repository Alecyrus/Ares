from celery import Celery
from environment import EnvironmentManager

app = Celery('environment_api', backend='redis://localhost:6379/3', broker = 'redis://localhost:6379/3')


handler = EnvironmentManager()

@app.task
def post(message):
    print(message)
    return handler.create(message)

@app.task
def delete(message):
    print(message)
    response = handler.delete(message)
    return response
