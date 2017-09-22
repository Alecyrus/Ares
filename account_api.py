from celery import Celery
from account import AccountsManager

app = Celery('acount_api', backend='redis://localhost:6379/1', broker = 'redis://localhost:6379/1')



@app.task
def post(message):
    handler = AccountsManager()
    print(message)
    return handler.create(message)

@app.task
def patch(message):
    handler = AccountsManager()
    print(message)
    return handler.update(message)

@app.task
def put(message):
    handler = AccountsManager()
    print(message)
    return handler.delete(message)
