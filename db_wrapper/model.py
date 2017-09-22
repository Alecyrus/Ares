# -*-coding:utf-8-*-
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy import Column, Integer

class TimeStampMixin(object):
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SoftDeleteMixin(object):
    '''A model instance with SoftDeleteMixin can use "soft_delete" method to mark
    it as "deleted". This method will flush this not commit the session automatically, so you
    have to call session.commit() to commit.'''
    deleted_at = Column(DateTime)
    deleted = Column(Integer, default=0)

    def soft_delete(self, session):
        '''Mark this object as deleted.'''
        self.deleted = 1
        self.deleted_at = datetime.now()
        session.add(self)
        # with session.begin(subtransactions=True):
        #     session.add(self)
        #     session.flush()

