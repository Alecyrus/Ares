from .config import *


@db
def query(model, session, outer, **kwargs):
    instances = session.query(model)
    instances = instances.filter_by(**kwargs)
    res = list()
    for instance in instances:
        d = instance.__dict__
        del(d['_sa_instance_state'])
        res.append(d)
    return res


@db
def query_one(model, session, outer, **kwargs):
    instances = session.query(model)
    instance = instances.filter_by(**kwargs).first()
    if instance:
        d = instance.__dict__
        del(d['_sa_instance_state'])
        return d
    else:
        return None

@db
def update(model, filter, new_value, session, outer):
    instances = session.query(model)
    instances = instances.filter_by(**filter)
    for instance in instances:
        for key, value in new_value.items():
            setattr(instance, key, value)
            print(instance.desc)
        session.add(instance)

@db
def update_one(model, filter, new_value, session, outer):
    instances = session.query(model)
    instance = instances.filter_by(**filter).first()
    for key, value in new_value.items():
        setattr(instance, key, value)
    session.add(instance)

@db
def insert(model, session, outer, **kwargs):
    instance = model(**kwargs)
    session.add(instance)
    try:
        session.flush()
        return instance.id
    except:
        return None


@db
def soft_delete(model, session, outer, **filter):
    instances = session.query(model)
    instances = instances.filter_by(**filter)
    for instance in instances:
        instance.soft_delete(session)

@db
def soft_delete_one(model, session, outer, **filter):
    instances = session.query(model)
    instance = instances.filter_by(**filter).first()
    instance.soft_delete(session)

@db
def delete(model, session, outer, **filter):
    instances = session.query(model)
    instance = instances.filter_by(**filter)
    for instance in instances:
        session.delete(instance)

@db
def delete_one(model, session, outer, **filter):
    instance = session.query(model).filter_by(**filter).first()
    session.delete(instance)
