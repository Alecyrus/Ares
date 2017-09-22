from celery import Celery
from fish import FishManager

app = Celery('tasks', backend='redis://localhost:6379/4', broker = 'redis://localhost:6379/4')


handler = FishManager()

@app.task
def post(message):
	#{"template":template_id,"region":region_id}
    return handler.build(message)
	
