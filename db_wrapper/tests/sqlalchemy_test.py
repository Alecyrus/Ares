
import sys, os.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# from brett_sqlalchemy import *
# Can not perform relative when it's parent module is not loaded, so I have to change the system's import path.
from main import *
import unittest
from sqlalchemy.ext.declarative import declarative_base
import os
import json
Base = declarative_base()

sql_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db_config.json')
sql_config = open(sql_config_path, 'r')
sql_config = json.load(sql_config)
connection_string = sql_config['server'] + '://' +  sql_config['user'] + ':' + sql_config['password'] + '@' + sql_config['address'] + '/' + sql_config['database'] + sql_config['extra']
mode = sql_config['mode']
echo = False
# if mode == 'develop' or 'debug':
#     echo = True
provider = ConnectionProvider(connection_string, echo=echo)
configure_provider(provider)
provider.start()
engine = provider._engine


class ModelA(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'test_model_a'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))


class ModelB(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'test_model_b'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True)


metadata = Base.metadata
metadata.create_all(engine)

class TestSession(unittest.TestCase):
    # @classmethod
    # def setupClass(cls):
    #     metadata = Base.metadata
    #     metadata.create_all(engine)
    #
    # def test_normal_session(self):
    #
    #     @db()
    #     def add_one(name, session):
    #         instance_a = ModelA(name=name)
    #         session.add(instance_a)
    #
    #     @db()
    #     def query_one(name, session):
    #         instance_a = session.query(ModelA).filter_by(name=name).first()
    #         if hasattr(instance_a, 'name'):
    #             return instance_a.name
    #         return None
    #
    #
    #     add_one('Eureka')
    #     name = query_one('Eureka')
    #     self.assertEqual(name, 'Eureka')

    def test_nest_transaction_(self):

        @db
        def insert_multi_success(session, outer):
            insert_one('Spring', outer=outer)
            insert_one('Summer', outer=outer)
            insert_one('Autumn', outer=outer)

        @db
        def insert_multi_fail(session, outer):
            insert_one('Winter', outer=outer)
            insert_one('Winter', outer=outer)
            insert_one('Peace', outer=outer)

        @db
        def insert_one(name, session, outer):
            instance_a = ModelB(name=name)
            session.add(instance_a)

        @db
        def query_one(name, session, outer):
            instance_a = session.query(ModelB).filter_by(name=name).first()
            if hasattr(instance_a, 'name'):
                return instance_a.name
            return None

        insert_multi_success()
        spring = query_one('Spring')
        summer = query_one('Summer')
        autumn = query_one('Autumn')

        self.assertEqual(spring, 'Spring')
        self.assertEqual(summer, 'Summer')
        self.assertEqual(autumn, 'Autumn')

        insert_multi_fail()
        winter = query_one('Winter')
        self.assertFalse(winter)


