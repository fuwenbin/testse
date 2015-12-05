'''
Created on 2015.7.24

@author: fuwenbin
'''


import wisegridlbaas
from neutron_lbaas.services.loadbalancer.drivers import abstract_driver
from oslo_log import log as logging
from neutron_lbaas.db.loadbalancer import loadbalancer_db as lb_db
from neutron.plugins.common import constants

VERSION = "1.0.0"
LOG = logging.getLogger(__name__)
class WisegridDriver(abstract_driver.LoadBalancerAbstractDriver):


    def __init__(self, plugin):
        LOG.debug("WisegridDriver:init version=%s",VERSION)
        self.plugin = plugin
        self.neutron_map = {
            'member': {
                'model': lb_db.Member,
                'delete_func': self.plugin._delete_db_member,
            },
            'pool': {
                'model': lb_db.Pool,
                'delete_func': self.plugin._delete_db_pool,
            },
            'vip': {
                'model': lb_db.Vip,
                'delete_func': self.plugin._delete_db_vip,
            },
        }
        self.wisegrid = wisegridlbaas.WisegridRestclient1_0(self)
        
    
    def _active(self, context, model_type, model_id,status_description=None):
        self.plugin.update_status(context,
                                  self.neutron_map[model_type]['model'],
                                  model_id,
                                  constants.ACTIVE,status_description)

    def _failed(self, context, model_type, model_id,status_description):
        self.plugin.update_status(context,
                                  self.neutron_map[model_type]['model'],
                                  model_id,
                                  constants.ERROR,status_description)
            
    def _db_delete(self, context, model_type, model_id):
        self.neutron_map[model_type]['delete_func'](context, model_id)

    def _hm_active(self, context, hm_id, pool_id):
        self.plugin.update_pool_health_monitor(context, hm_id, pool_id,
                                               constants.ACTIVE)

    def _hm_failed(self, context, hm_id, pool_id):
        self.plugin.update_pool_health_monitor(context, hm_id, pool_id,
                                               constants.ERROR)

    def _hm_db_delete(self, context, hm_id, pool_id):
        self.plugin._delete_db_pool_health_monitor(context, hm_id, pool_id)
    
    def _make_member_dict(self, member, fields=None):
        res = {'id': member['id'],
               'tenant_id': member['tenant_id'],
               'pool_id': member['pool_id'],
               'address': member['address'],
               'port': member['protocol_port'],
               'weight': member['weight'],
               'admin_state_up': member['admin_state_up'],
               'status': member['status'],
               'status_description': member['status_description']}
        return res
    def get_members(self,context,pool_id):
        members =  context.session.query(lb_db.Member).filter_by(pool_id = pool_id).all()
        return [self._make_member_dict(c) for c in members]
    
    def create_vip(self, context, vip):
        LOG.debug("CREATE VIP !!!!!!!########")
        self.wisegrid.create_vip(context,vip)
        
        
    def update_vip(self, context, old_vip, vip):
        self.wisegrid.update_vip(context,old_vip,vip)
        

    def delete_vip(self, context, vip):
        self.wisegrid.delete_vip(context,vip)
        

    def create_pool(self, context, pool):
        LOG.debug("Create pool !!!!!!!!!!!!!################")
        self.wisegrid.create_pool(context,pool) 

    def update_pool(self, context, old_pool, pool):
        self.wisegrid.update_pool(context,old_pool,pool)
            
    def delete_pool(self, context, pool):
        self.wisegrid.delete_pool(context, pool)

    def stats(self, context, pool_id):
        pass

    def create_member(self, context, member):
        self.wisegrid.create_member(context,member)

    def update_member(self, context, old_member, member):

        self.wisegrid.update_member(context,old_member,member)

    def delete_member(self, context, member):
        self.wisegrid.delete_member(context,member)

    def update_pool_health_monitor(self, context,
                                   old_health_monitor,
                                   health_monitor,
                                   pool_id):
        self.wisegrid.update_pool_health_monitor(context, old_health_monitor, health_monitor, pool_id)

    def create_pool_health_monitor(self, context,
                                   health_monitor,
                                   pool_id):
  
        self.wisegrid.create_pool_health_monitor(context, health_monitor, pool_id)

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        self.wisegrid.delete_pool_health_monitor(context, health_monitor, pool_id)
