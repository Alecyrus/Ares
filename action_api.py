from celery import Celery
from action import ServerAction

app = Celery('actipn_api', backend='redis://localhost:6379/2', broker = 'redis://localhost:6379/2')


handler = ServerAction()

@app.task
def put(message):
    print(message)
    return handler.stop(message)

@app.task
def patch(message):
    print(message)
    return handler.get(message)

@app.task
def post(message):
    print(message)
    return handler.start(message)
