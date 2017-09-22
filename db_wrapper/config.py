import sys
import os
sys.path.append(os.path.dirname(__file__))
import configparser
from main import *

# Start the Database Connection
config = configparser.ConfigParser()
config.read('setting.conf')
database_config = config['database']
connection_string = database_config['server'] + '://' +  database_config['user'] + ':' \
                    + database_config['password'] + '@' + database_config['address'] + '/' \
                    + database_config['database'] + database_config['extra']


provider = ConnectionProvider(connection_string)
configure_provider(provider)
provider.start()
engine = provider._engine


region_list = config['basic']['region'].replace(' ','').split(',')
for region in region_list:
    region_config = config[region]
    neutron_connection_string = region_config['db_backend'] + '://' + region_config['db_user'] \
                            + ':'  + region_config['db_password'] +"@"+ region_config['controller_ip'] \
                            + '/' + region_config['db_database']
    configure_neutron_engine(neutron_connection_string, region)
    

