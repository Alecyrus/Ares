# -*-coding:utf-8-*-

from models import *
from orm_wrapper import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import String, Column, Integer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest

Base = declarative_base()

class ModelA(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'model_a'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))

class Test(unittest.TestCase):
    session = None
    engine = None

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('mysql://root:p2314h@localhost/test', echo=True)
        Session = sessionmaker(bind=cls.engine, query_cls=Query)
        cls.session = Session()
        metadata = Base.metadata
        metadata.create_all(cls.engine)
        instance_a = ModelA(name='test_instance_1')
        cls.session.add(instance_a)
        added_model_2 = ModelA(name='test_instance_2')
        cls.session.add(added_model_2)
        added_model_3 = ModelA(name='test_instance_2')
        cls.session.add(added_model_3)
        cls.session.commit()

    @classmethod
    def tearDownClass(cls):
        all = cls.session.query(ModelA)
        for instance in all:
            cls.session.delete(instance)
        cls.session.commit()

    def setUp(self):
        self.session = self.__class__.session

    def test_add(self):
        retrieved_instance = self.session.query(ModelA).filter_by(name='test_instance_1').first()
        self.assertEqual(retrieved_instance.name, 'test_instance_1')

    def test_timestamp(self):
        retrieved_instance = self.session.query(ModelA).filter_by(name='test_instance_1').first()
        self.assertTrue(retrieved_instance.created_at)

    def test_soft_delete_model(self):
        retrieved_instance = self.session.query(ModelA).filter_by(name='test_instance_1').first()
        retrieved_instance.soft_delete(self.session)
        self.session.commit()
        retrieved_instance = self.session.query(ModelA).filter_by(name='test_instance_1').first()
        self.assertTrue(retrieved_instance.deleted)
        self.assertTrue(retrieved_instance.deleted_at)

    def test_soft_delete_query(self):
        retrieved_instances = self.session.query(ModelA).filter_by(name='test_instance_2')
        retrieved_instances.soft_delete()
        self.session.commit()
        retrieved_instances = self.session.query(ModelA).filter_by(name='test_instance_2')
        for instance in retrieved_instances:
            self.assertTrue(instance.deleted)
            self.assertTrue(instance.deleted_at)

if __name__ == '__main__':
    unittest.main()