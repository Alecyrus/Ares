import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from db_wrapper import execute

#
# sql = 'create table test_model' \
#       '(' \
#       'id int,' \
#       'name varchar(32)' \
#       ');'
# execute(sql)

insert = 'insert into test_model ' \
    '(id, name) values (1, "fuck");'

query = 'select * from test_model ' \
        'where id = 1;'
# execute(insert)
res = execute(query)

print(res.id)
