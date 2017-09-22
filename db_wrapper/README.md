# sqlalchemy-handywrapper / db-wrapper
db-wrapper是对于SQLAlchemy做的又一层封装，提供了常用的软删除功能，时间戳功能，以及自动事务管理的功能。

### 软删除功能
软删除功能位于main.py的SoftDeleteMixin类中。要实现软删除功能，创建的Model需要继承自SoftDeleteMixin类。继承自SoftDeleteMixin的Model的实例可以调用soft_delete方法，对于该实例进行软删除。SoftDeleteMixin会自动创建一个子事务（见下），不过这并不会影响事务的正常提交。

### 时间戳功能
时间戳功能位于main.py的TImeStampMixin类种。要实现时间戳功能，创建的Model需要继承自TimeStampMixin类。继承自TimeStampMixin类的Model的实例将拥有created_at和updated_at两个属性，对应数据库种created_at和updated_at两列。时间戳是会自动更新的。

### 事务管理
事务管理的核心思想是用户无需手动地控制某个事务的开始或者回滚，对于一组数据库操作，将其定义到一个函数中以方便功能管理，并且将函数用装饰器@db修饰，即实现了事务的自动管理功能。目前的功能是，如果事务执行过程中，不管是其中某个数据库操作出现错误或者其中某个子事务出现错误，则整个事务都会回退。


# 示例代码：

- 建立Model以及对应的数据库表

``` Python

from db_wrapper import Base, TimeStampMixin, SoftDeleteMixin
from db_wrapper import engine
from sqlalchemy import Integer, String, Column, DateTime


# 建立Model
class ExampleModel(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'examplemodel'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    desc = Column(String(50))

# 创建数据库中的表
# 调用metadata.createall()会在数据库中创建继承自Base的所有Model对应的数据库表。
# 如果数据库表已经存在则不会再次创建。亦即，该语句只会在数据库尚未创建的时候真正执行操作。
metadata = Base.metadata
metadata.create_all(engine)

```


- 数据库提供的api的用法：
db_wrapper模块提供了基本的增删改查的接口:

@db
def query(model, session, outer, **kwargs)
查询并返回符合筛选条件的数据库记录，需要传入的参数为model和**kwargs（作为筛选条件），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def query_one(model, session, outer, **kwargs)
查询并返回符合筛选条件的数据库第一条记录，需要传入的参数为model和**kwargs（作为筛选条件），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def update(model, filter, new_value, session, outer)
更新符合筛选条件的数据库记录。，需要传入的参数为model、filter（filter为一个词典，new_value也是一个词典），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def update_one(model, filter, new_value, session, outer)
更新符合筛选条件的数据库记录的第一条。，需要传入的参数为model、filter（filter为一个词典，new_value也是一个词典），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def insert(model, session, outer, **kwargs)
插入一条数据库记录，需要传入的参数为model，**kwargs（以关键字参数形式传入，描述了要插入的记录的各项属性），如果该函数被包含在另一个有@db修饰的数据库操作函数中，那么调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def soft_delete(model, session, outer, **filter)
软删除符合筛选条件的数据库记录，需要传入的参数为model和**kwargs（作为筛选条件），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。

@db
def soft_delete_one(model, session, outer, **filter):
软删除符合筛选条件的数据库记录的第一条，需要传入的参数为model和**kwargs（作为筛选条件），session参数无需传入。如果该函数被包含在另一个由@db修饰的数据库操作函数中，那么在调用该函数的时候要以关键字参数形式传入outer=outer。








# 示例代码：

- 建立Model以及对应的数据库表

``` Python
# orm_models.py

from dbwrapper.api import Base
from dbwrapper.api import TimeStampMixin, SoftDeleteMixin
from dbwrapper.api import Integer, String, Column, DateTime
from dbwrapper.api import create_engine

class ExampleModel(Base, TimeStampMixin, SoftDeleteMixin):
    __tablename__ = 'examplemodel'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    desc = Column(String(255))

# 连接数据库
# echo=True的情况下可以在控制台上看到真正执行的SQL语句。适合用于调试。echo默认值为False，生产环境中可关闭echo
engine = create_engine('mysql://root:password@host/test_db', echo=True)
# 调用metadata.createall()会在数据库中创建继承自Base的所有Model对应的数据库表。
# 如果数据库表已经存在则不会再次创建。亦即，该语句只会在数据库尚未创建的时候真正执行操作。
metadata = Base.metadata
metadata.create_all(engine)

```

- 自定义数据库操作

``` Python

# 如果要进行比较复杂的操作，可以自定义数据库操作

from db_wrapper import db

# 用@db修饰的自定义数据库函数，必须要有session和outer这两个参数。

@db
def get_user_name(id, session, outer):
    # 无需传入session参数，只要经过db修饰，那么就可以使用session
    instance = session.query(User).filter_by(id=id)
    return instance.name


# 嵌套的事务

# 如果一个事务过程中需要执行多个子事务，那么定义子事务的函数，在该事务过程中被调用时，需要传入关键字参数outer=outer。
@db
def get_user_email(id, session, outer):
    instance = session.query(User).filter_by(id=id)
    return id.email


@db
def get_user_information(id, session, outer):
    name = get_user_name(id, outer=outer)
    email = get_user_email(id, outer=outer)
    return (name, email)
# 对于像get_user_information这样的嵌套的事务，内层的函数在调用时需要传入outer=outer，否则内层的事务将会是独立的，而非作为外层事务的子事务。
# 如果内层事务中的任一步出错，整个事务至此都会回退，并且事务之后的操作也不会执行。目前并没有savepoint功能。

```

### 数据库的配置
数据库的配置文件已经统一到ares.conf中。