# -*-coding:utf-8-*-

from datetime import datetime
import sqlalchemy.orm
from sqlalchemy.sql.expression import literal_column


class Query(sqlalchemy.orm.query.Query):
    '''A SQLAlchemy Query object can perform such method as "delete()", "update()" to
    delete or update data of these proxy objects in the Query. Now we define a method
    "soft_delete()" to mark status of these proxy objects as "deleted" but not actually
    delete them.'''
    def soft_delete(self):
        return self.update({'deleted': 1,
                            'updated_at': literal_column('updated_at'),
                            'deleted_at': datetime.now()})

class Session(sqlalchemy.orm.session.Session):
    '''Session subclass used in this library.'''

def get_maker(engine, autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       class_=Session,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit,
                                       query_cls=Query)
