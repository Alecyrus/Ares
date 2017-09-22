# -*-coding:utf-8-*-

from models import *
from .. import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy import String, Column, Integer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# from session import *
import unittest
import gc

# ONE VERY IMPORTANT THING:
# SINCE ALL SESSIONS BUILT BY SESSION_MAKER IS IN AUTOCOMMIT MODE
# EVERY TIME AFTER FINISHING USING A SESSION TO DO SOME QUERY OR INSERT
# BE SURE TO CALL SESSION.COMMIT() OR SESSION.ROLLBACK()
# SO THAT NO UNNECESSARY SUBTRANSACTION BEGINS.

Base = declarative_base()
connection_provider = ConnectionProvider('mysql://root:p2314h@localhost/test')
configure_provider(connection_provider)
writer = get_writer()
reader = get_reader()

class ModelA(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'model_a'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))


class ModelB(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'model_b'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True)



class TestSession(unittest.TestCase):
    session = None
    engine = None
    context = SessionContext()
    writer_pass = False
    reader_pass = False

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('mysql://root:p2314h@localhost/test', echo=True)
        # cls.Session = sessionmaker(bind=cls.engine, query_cls=Query)
        cls.Session = get_maker(engine=cls.engine)
        metadata = Base.metadata
        metadata.create_all(cls.engine)


    @classmethod
    def tearDownClass(cls):
        # cls.session.begin()
        # all = cls.session.query(ModelA)
        # for instance in all:
        #     cls.session.delete(instance)
        # cls.session.commit()
        session = cls.Session()
        session.begin()
        all_a = session.query(ModelA)
        for instance_a in all_a:
            session.delete(instance_a)
        all_b = session.query(ModelB)
        for instance_b in all_b:
            session.delete(instance_b)
        session.commit()

    def test_reader(self):

        @writer
        def add_one(context, foo):
            instance_a = ModelA(name=foo)
            context.session.add(instance_a)
            return 1


        @reader
        def reader_one(context, foo, bar):
            retrieved_instance = context.session.query(ModelA).filter_by(name=foo).first()
            added_instance = ModelB(name=bar)
            context.session.add(added_instance)
            return retrieved_instance.name

        context = self.__class__.context
        self.assertEqual(add_one(context, 'test_instance_1'), 1)
        retrieved_name = reader_one(context, 'test_instance_1', 'unique')
        self.assertEqual(retrieved_name, 'test_instance_1')

        session = self.__class__.Session()
        retrieved_instance_2 = session.query(ModelB).filter_by(name='unique').first()
        session.rollback()
        self.assertFalse(retrieved_instance_2)

    def test_softdelete(self):
        @writer
        def s_d(context, foo):
            instance_a = context.session.query(ModelA).filter_by(name=foo).first()
            instance_a.soft_delete(context.session)

        @reader
        def reader_one(context, foo):
            retrieved_instance = context.session.query(ModelA).filter_by(name=foo).first()
            return retrieved_instance.deleted

        context = self.__class__.context
        s_d(context, 'test_instance_1')
        retrieved_deleted = reader_one(context, 'test_instance_1')
        self.assertEqual(retrieved_deleted, 1)

    def test_nested_transaction(self):
        @writer
        def out_writer(context, foo):
            inner_writer(context, foo)
            inner_writer(context, foo)

        @writer
        def inner_writer(context, foo):
            added_instance = ModelB(name=foo)
            context.session.add(added_instance)

        context = self.__class__.context
        # self.assertRaises(Exception, out_writer, context, 'unique')
        out_writer(context, 'unique')

        session = self.__class__.Session()
        retrieved_instance = session.query(ModelB).filter_by(name='unique').first()
        session.rollback()

        self.assertFalse(retrieved_instance)

    def test_nested_transaction_2(self):
        @writer
        def out_writer(context, foo, bar):
            inner_writer(context, foo)
            inner_writer(context, bar)

        @writer
        def inner_writer(context, foo):
            added_instance = ModelB(name=foo)
            context.session.add(added_instance)

        context = self.__class__.context
        out_writer(context, 'non_unique', 'neither_unique')
        session = self.__class__.Session()
        retrieved_instance = session.query(ModelB).filter_by(name=u'non_unique').first()
        session.rollback()
        # retrieved_instance = self.session.query(ModelB).filter_by(name=u'non_unique').first()
        self.assertTrue(retrieved_instance)


if __name__ == '__main__':
    unittest.main()
    print("garbage object num:")
    print(len(gc.garbage))
    a = 1