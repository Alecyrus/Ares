
from db_wrapper.api import *
from db_wrapper.model import TimeStampMixin, SoftDeleteMixin
from db_wrapper.api import Column, String, Integer, DateTime, Text, engine
#from db_wrapper import Text
from sqlalchemy import ForeignKey, SmallInteger, BigInteger
#from db_wrapper import engine


Base = declarative_base()
class Software(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'software'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    resource_path = Column(String(255))
    description = Column(String(255), nullable=False)
    is_public = Column(Integer, nullable=False)
    author = Column(Integer, ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)



class User(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    passwd = Column(String(255), nullable=False)
    salt = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    op_user = Column(String(50), nullable=True)
    op_username = Column(String(50), nullable=True)
    op_project = Column(String(50), nullable=True)
    op_passwd = Column(String(50), nullable=True)
    region_id = Column(String(50), nullable=True)
    stu_number = Column(String(255))
    phone = Column(String(255))
    resource_path = Column(String(255))

class Image(Base, TimeStampMixin, SoftDeleteMixin):
    # Base Image Table
    __tablename__ = 'image'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    author = Column(Integer, ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    mirror_op_id = Column(String(255))
    resource_path = Column(String(255))
    container_format = Column(String(50))
    disk_format = Column(String(50))


class ALLImage(Base, TimeStampMixin, SoftDeleteMixin):
    # Base Image Table
    __tablename__ = 'all_image'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    #author = Column(Integer, ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    region_id = Column(String(255))
    mirror_op_id = Column(String(255))
    resource_path = Column(String(255))
    container_format = Column(String(50))
    disk_format = Column(String(50))
    disk = Column(Integer, nullable=False)
    ram = Column(Integer, nullable=False)
    cpu = Column(Integer, nullable=False)
    flavor_op_id = Column(String(255))
    base_image_id = Column(Integer, ForeignKey('image.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True)



class Flavor(Base, TimeStampMixin, SoftDeleteMixin):
    # Flavor options that shown in the front end
    __tablename__ = 'flavor'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    author = Column(Integer, ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    ram = Column(Integer, nullable=False)
    cpu = Column(Integer, nullable=False)
    flavor_op_id = Column(String(255))

############################################################################
# DOWN BELOW ARE MODELS OF THE TARGET SYSTEM.
############################################################################

class Template(Base, TimeStampMixin,SoftDeleteMixin):
    """A template contains the information of a network topology of a course, environment or vulnerability."""
    __tablename__ = 'template'
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_list = Column(Text)
    sw_list = Column(Text)
    flavor_list = Column(Text)
    state = Column(String(255))




class Target(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'target'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=True)
    template = Column(Integer, ForeignKey('template.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    user = Column(Integer, ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    state = Column(Integer, nullable=False)
    net_op_id = Column(String(50), nullable=True)
    extra1 = Column(String(255), nullable=True)
    extra2 = Column(String(255), nullable=True)


class VM(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'vm'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=True)
    ip_address = Column(String(255), nullable=True)
    vm_op_id = Column(String(50), nullable=False)
    ip_address = Column(String(255), nullable=True)
    target = Column(Integer, ForeignKey('target.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    user = Column(Integer, ForeignKey('user.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    state = Column(Integer, nullable=False)
    url = Column(String(255), nullable=True)
    extra = Column(String(255), nullable=True)


class Router(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'router'
    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(50), nullable=True)
    rt_op_id = Column(String(50), nullable=False)
    target = Column(Integer, ForeignKey('target.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=True)
    user = Column(Integer, ForeignKey('user.id'), nullable=False)
    extra = Column(String(255), nullable=True)


class Port(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'port'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=True)
    net = Column(Integer, nullable=True)
    router = Column(Integer, nullable=True)
    target = Column(Integer, ForeignKey('target.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=True)
    extra = Column(String(255), nullable=True)
    ip_address = Column(String(255), nullable=False)
    port_op_id = Column(String(255), nullable=False)
    is_interface = Column(Integer, nullable=False)




class SubNet(Base, SoftDeleteMixin, TimeStampMixin):
    __tablename__ = 'subnet'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    target = Column(Integer, ForeignKey('target.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    cidr = Column(String(50), nullable=True)
    net_op_id = Column(String(50), nullable=True)
    user = Column(Integer, ForeignKey('user.id'), nullable=False)
    extra = Column(String(255), nullable=True)


metadata = Base.metadata
metadata.create_all(engine)

