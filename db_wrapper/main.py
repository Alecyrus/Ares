import os.path, sys
from datetime import datetime
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import literal_column
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
import functools
import logging
import logging.config
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import cloghandler
from pprint import pprint
#import MySQLdb
import pymysql


# Config the Logger
# Use the sqlalchemy.engine logger, but add a handler so that the logger would write it into logfile.

logging.config.fileConfig('logging.ini')
db_logger = logging.getLogger('sqlalchemy.engine')
db_logger.setLevel(logging.WARNING)
# handler = logging.FileHandler('log/database.log')
handler = cloghandler.ConcurrentRotatingFileHandler('log/database.log')
handler.level = logging.DEBUG
handler.formatter=logging.Formatter('%(asctime)s %(levelname)s %(module)s %(message)s')
db_logger.addHandler(handler)

# db_logger.info('yes')




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
    def __init__(self, *args, **kwargs):
        self.execute_remaining = True
        super().__init__(*args, **kwargs)


def get_maker(engine, autocommit=True, expire_on_commit=False):
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       class_=Session,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit,
                                       query_cls=Query)

class ConnectionProvider(object):
    '''This Connection Provider doesn't only provide the sqlalchemy "connection",
    it is an object that stores all information used to connect to sqlbackend.
    It also maintains references to sqlalchemy connection, session, transaction,
    sessionmaker, etc.that will be used in programs.'''

    def __init__(self, sqlbackend, echo=False):

        # the real string used to connect to the sqlbackend
        self.sqlbackend = sqlbackend
        self._started = False
        self.echo=False

    def start(self, **kwargs):
        if self._started:
            return

        self._engine = sqlalchemy.create_engine(self.sqlbackend, echo=self.echo)
        self._sessionmaker = get_maker(engine=self._engine, **kwargs)
        self._started = True

    def create_connection(self):
        if not self._started:
            self.start()
        return self._engine.connect()

    def create_session(self, bind=None, **kw):
        if not self._started:
            self.start()

        # In case that you need to bind the session to another engine
        if bind:
            kw['bind'] = bind
        return self._sessionmaker(**kw)

def get_connection_provider(sqlbackend, echo=False):
    '''Get a ConnectionProvider object by database backend'''
    return ConnectionProvider(sqlbackend, echo=echo)

_theProvider = None
def configure_provider(provider):
    global _theProvider
    _theProvider = provider

class SessionContext(object):
    def __init__(self, root=None, parent=None, provider=None):
        if root is None:
            self.root = self
            self.outermost = True
            if provider is None:
                global _theProvider
                self.provider = _theProvider

            self.session = self.provider.create_session()

            self.parent = None
        else:
            if isinstance(parent, SessionContext) and isinstance(root, SessionContext):
                self.root = root
                self.parent = parent
                self.provider = self.root.provider
                self.session = self.root.session
                self.outermost = False
            else:
                raise ValueError('Wrong Definition of a SessionContext!')

    def end_session(self):
        try:
            self.session.commit()
        except Exception as e:
            self.session.execute_remaining = False
            self.session.rollback()
            raise


def db(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        # outer_context = kwargs.get('context')
        outer_context = kwargs.pop('outer', None)
        res = None

        if not outer_context:
            Context = SessionContext()
        else:
            Context = SessionContext(root=outer_context.root, parent=outer_context)

        if Context.session.execute_remaining:
            try:
                Context.session.begin(subtransactions=True)
                res = func(session=Context.session, outer=Context, *args, **kwargs)
                Context.end_session()
            except Exception as e:
                Context.session.rollback()
                db_logger.error(e)
            finally:
                if Context.outermost == True:
                    Context.session.close()
                    Context.session = None
                # In order to easily GC
                Context = None
        return res
    return wrapper


#
# @db
# def foo(session, outer=None):
#     bar(outer=outer)
#
# @db
# def bar(session, outer):
#     pass
#
# foo()

neutron_engines = {}

def configure_neutron_engine(backend, region):
    global neutron_engines
    neutron_engine = create_engine(backend)
    neutron_engines[region] = neutron_engine

def execute(sql, region):
    global neutron_engines
    s = text(sql)
    neutron_engine = neutron_engines[region]
    res = neutron_engine.execute(s)
    if res.returns_rows:
        return res.fetchall()
    return None
