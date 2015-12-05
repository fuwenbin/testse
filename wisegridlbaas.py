#-*- coding:utf-8 -*-

__author__ = 'root'
import httplib
import json
import ssl
from neutron_lbaas.db.loadbalancer import loadbalancer_db as lb_db
import exceptions as w_ex
from oslo_log import log as logging
LOG = logging.getLogger(__name__)
data_style = ".json"
DRIVER_NAME = 'wisegrid'
class WiseClientBase(object):
    def __init__(self, host='192.168.10.50',port='10443'):
        self.host = host
        self.port = port
        self.token = None
        self.url_prefix = '/'
        self.cer_path = 'dkks.cer'


    def _do_request(self, method, action, body=None):
        conn = httplib.HTTPSConnection(self.host, self.port
#                                        ,context = ssl._create_unverified_context()
                                       )
        url = self.url_prefix + action
        headers = {}
        if self.token:
            headers['key'] = self.token
        headers['content-type'] = 'application/json'
        
        if body is not None:
            body = json.dumps(body)
            
        conn.request(method, url, body, headers)
        res = conn.getresponse()
        print "method:%s,action:%s,body:%s"%(method,action,body)
        if res.status in (httplib.OK,
                          httplib.CREATED,
                          httplib.ACCEPTED,
                          httplib.NO_CONTENT):
            return res
        raise w_ex.WisegridLBaasException()



    def _do_request_read(self, method, action,body=None):
        res = self._do_request(method, action,body)
        return json.loads(res.read())

class WisegridRestclient1_0(WiseClientBase,lb_db.LoadBalancerPluginDb):
    path_keygen = 'rest/keygen'+data_style

    path_pool = 'rest/pool'      # operate pool; 

    path_vserver = 'rest/vserver' # operate vip;

    path_healthcheck = 'rest/healthcheck'   # operate healthmonitor

    path_schedule = 'rest/sched'   #why use rest/slb_schedule/ping??
    
    def __init__(self,driver, host='192.168.10.50',port='10443'):
        super(WisegridRestclient1_0, self).__init__(host, port)
        self.driver = driver
        self._get_tokenkey()
        
    def _get_tokenkey(self):
        '''get the wisegrid token'''
        import md5
        
        md = md5.new()
        user = "admin"
        passwd = "sinogrid"
        md.update(user)
        user = md.hexdigest()
        
        md = md5.new()
        md.update(passwd)
        passwd = md.hexdigest().upper()
        uri = self.path_keygen+"?"+"username="+user+"&password="+passwd
        res =  self._do_request_read('GET',uri,"" )
        data = res
        if data.has_key('key'):            
            self.token = data['key']
            print "validate success , token is :%s"%self.token
        else:
            raise w_ex.WisegridLBaasException("Wisegrid lbaas keygen fail!!!!")
    
    def _update_status(self,context,model_type,model_id,reps):
        if reps and reps.has_key('result'):
            if reps['result']['success']=='true':
                self.driver._active(context,model_type,model_id)
                return
        LOG.warning("has error:%s"%reps)
        if reps.has_key('error'):
            message = reps['error']['message']
        else:
            message = reps['result']['message']
        self.driver._failed(context, model_type, model_id,message)
    
    def get_pool_from_wisegrid(self,poolname):
        path = self.path_pool+"/"+poolname+data_style
        response = self._do_request_read("GET", path, "")
        return response
    
    def _get_health_monitor_type(self,context,health_monitors):
        health_id = health_monitors[0] if health_monitors else None
        #if not health_id:
        #    return None
        #health_monitor = super(WisegridRestclient1_0, self).get_health_monitor(context,health_id)
        return health_id
    def _get_subnet(self,context,subnet_id):
        subnet = super(WisegridRestclient1_0, self)._core_plugin.get_subnet(context, subnet_id)
        return subnet    
    
    def create_pool(self,context,pool):
        '''
        '''
        params={"pool":{
            "name":pool['name'],
            "type":"ipv4",
        }}
        path = self.path_pool + data_style
        response = self._do_request_read("POST", path, params)
        self._update_status(context,'pool',pool['id'],response)
        
    def update_pool(self,context,old_pool,pool,is_pool=True):
        '''
        '''
        if is_pool:
            if old_pool['name'] != pool['name']:
                del old_pool['protocol']
                del old_pool['members']
                del old_pool['subnet_id']
                del old_pool['tenant_id']
                del old_pool['health_monitors_status']
                del old_pool['health_monitors']
                del old_pool['id']
                del old_pool['vip_id']
                del old_pool['provider']
                db_pool = {'pool':old_pool}
                super(WisegridRestclient1_0, self).update_pool(context,pool['id'],db_pool)
                raise w_ex.UnsupportOperation(operation="update pool name")
                #self.driver._failed(context, 'pool', pool['id'], "wisegrid can't allow update the pool name!!")
            if old_pool['lb_method'] != pool['lb_method']:
                self.update_vip(context, old_pool, pool)
        
        path = self.path_pool+"/"+old_pool['name']+ data_style
        params={"pool":{
            "name":pool['name'],
            "type":"ipv4",
            }}
        if pool.has_key('members'):
            params["pool"]['realServer'] = pool['members']
        else:
            params['pool']['realServer'] = []
            
        if pool.has_key('health_monitors'):
            params['pool']['healthcheck'] = pool['health_monitors'][0] if pool['health_monitors'] else None
        response = self._do_request_read("PUT", path, params)
        return response
        
    def delete_pool(self,context,pool):
        path = self.path_pool+'/'+pool['name']+ data_style
        response = self._do_request_read("DELETE", path)
        if response and response.has_key('result'):
            self.driver._db_delete(context, 'pool', pool['id'])
        
    def create_vip(self,context,vip):
        '''
        '''
        import pdb
        pdb.set_trace()
        pool = self.driver.plugin.get_pool(context, vip['pool_id'])
        subnet = self._get_subnet(context, pool['subnet_id'])
        params = {"vserver":{
            "name": vip['name'],
            "type":"ipv"+str(subnet['ip_version']),
            "address":vip['address'],
            "port": vip['protocol_port'],
            "protocol":vip['protocol'],
            "pool": pool['name'],
            "sched": 'rr',#pool['lb_method'],
            "enable":"on",
        }}
        path = self.path_vserver + data_style
        response = self._do_request_read("POST", path, params)       
        self._update_status(context, 'vip', vip['id'], response)

    def update_vip(self,context,old_vip,vip):
        import pdb
        pdb.set_trace()
        if old_vip['name'] !=vip['name']:
            del old_vip['protocol']
            del old_vip['id']
            del old_vip['status_description']
            del old_vip['tenant_id']
            del old_vip['address']
            del old_vip['protocol_port']
            db_vip = {'vip':old_vip}
            super(WisegridRestclient1_0, self).update_vip(context,vip['id'],db_vip)
            raise w_ex.UnsupportOperation(operation="update vip name")
        
        old_pool = self.driver.plugin.get_pool(context, old_vip['pool_id'])
        pool = self.driver.plugin.get_pool(context, vip['pool_id'])
        if old_pool['provider'] != pool['provider']:
            raise w_ex.UnsupportOperation(operation="across differebt provider")
        subnet = self._get_subnet(context, pool['subnet_id'])
        params = {"vserver":{
            "name": vip['name'],
            "type":"ipv"+str(subnet['ip_version']),
            "address":vip['address'],
            "port": vip['protocol_port'],
            "protocol":vip['protocol'],
            "pool": pool['name'],
            "sched": 'rr', #pool['lb_method']
            "enable":"on",
            "persistent":"off"     #'session_persistence': {'type': u'SOURCE_IP'}
            }}        
        path = self.path_vserver + '/' + old_vip['name']+data_style
        response =  self._do_request_read("PUT",path, params)
        self._update_status(context, 'vip', vip['id'], response)
        
    def delete_vip(self,context,vip):
        path = self.path_vserver + '/' + vip['name'] + data_style
        #response =  self._do_request_read("DELETE", path)
#        if response and response.has_key('result'):
        self.driver._db_delete(context, 'vip', vip['id'])
   
    def create_member(self,context,member):
        pool = self.driver.plugin.get_pool(context,member['pool_id'])
        members = self.driver.get_members(context,member['pool_id'])
        pool['members'] = members
        response = self.update_pool(context, pool, pool,False)
        self._update_status(context, 'member', member['id'], response)
        
    def update_member(self,context,old_member,member):
        old_pool = self.driver.plugin.get_pool(context,old_member['pool_id'])
        pool = self.driver.plugin.get_pool(context,member['pool_id'])
        if old_pool['provider'] != pool['provider']
            old_members = self.driver.get_members(context,old_member['pool_id'])
            members = self.driver.get_members(context,member['pool_id'])
            old_pool['members']=old_members
            pool['members'] = members
            self.update_pool(context, old_pool, old_pool, False)
            self.update_pool(context, pool, pool, False)
        else:
            w_ex.UnsupportOperation(operation="across differebt provider")
        	  	
    def delete_member(self,context,member):
        pool = self.driver.plugin.get_pool(context, member['pool_id'])
        members = self.driver.get_members(context,member['pool_id'])
        delete_indext = 0
        for index in range(len(members)):
            if member['address'] == members[index]['address']:
                delete_indext = index
        del members[delete_indext]
        pool['members'] = members
        response = self.update_pool(context, pool, pool,False)
        if response and response.has_key('result'):
            self.driver._db_delete(context, 'member', member['id'])
    
    def _create_healthcheck(self,health_monitor):
        params = {"healthcheck":{
        	"name":health_monitor['type'],
          "type":health_monitor['type'],
          "interval":health_monitor['delay'],
          "intermission":100,  # chixu time
          "retry":health_monitor['max_retries'],
          "timeout":health_monitor['timeout'],
        	} 
        }
        path = self.path_healthcheck + data_style
        response =  self._do_request_read("POST", path,params)
        if response.has_key('error'):
            raise w_ex.WisegridLBaasException()
        LOG.debug("create health_monitor :%s"%response)
        return params
    
    def _update_healthcheck(self,health_monitor):
        params = {"healthcheck":{
        	"name": health_monitor['id'],
          "type":health_monitor['type'],
          "interval":health_monitor['delay'],
          "intermission":30,  # chixu time
          "retry":health_monitor['max_retries'],
          "timeout":health_monitor['timeout'],
        	} 
        }
        path = self.path_healthcheck + '/' + health_monitor['id'] + data_style
        response =  self._do_request_read("POST", path,params)
        if response.has_key('error'):
            raise w_ex.WisegridLBaasException()
        LOG.debug("update health_monitor :%s"%response)
    
    def create_pool_health_monitor(self,context,health_monitor,pool_id):
        pool = self.driver.plugin.get_pool(context, pool_id)
        wise_pool = self.get_pool_from_wisegrid(pool['name'])
        if wise_pool['pool'].has_key('healthcheck'):
            raise w_ex.UnsupportOperation(operation="add more than one healthcheck")
        filters = {'pool_id':pool_id}
        members = self.driver.plugin.get_members(context,filters,['address','protocal_port'])
        self._create_healthcheck(health_monitor)        
        pool['members'] = members
        response = self.update_pool(context, pool, pool, False)
        if response and response.has_key('result'):
            if response['result']['success']=='true':
                self.driver._hm_active(context,health_monitor['id'],pool_id)
        else:
            self.driver._hm_failed(context,health_monitor['id'],pool_id)
        
    def update_pool_health_monitor(self,context,old_health_monitor,health_monitor,pool_id):
        #pool = self.driver.plugin.get_pool(context,pool_id, ['name','lb_method'])
        #wise_pool = self.get_pool_from_wisegrid(pool['name'])
        #if wise_pool['pool']['healthcheck']:
            #raise w_ex.UnsupportOperation(operation="add more than one healthcheck")
        #members = self.driver.plugin.get_members(context,filters,['address','protocal_port'])
        #pool['members'] = members
        self._update_healthcheck(health_monitor)
        #response = self.update_pool(context, pool, pool, False)
        #if response and response.has_key('result'):
            #self.driver._hm_active(context,health_monitor['id'],pool_id)
        #else:
            #self.driver._hm_failed(context,health_monitor['id'],pool_id)
    
    def delete_pool_health_monitor(self,context,health_monitor,pool_id):
        filters = {'pool_id':pool_id}
        pool = self.driver.plugin.get_pool(context, pool_id, ['name','lb_method'])
        members = self.driver.plugin.get_members(context,filters,['address','protocal_port'])
        pool['members'] = members
        pool['health_monitors'] = []
        response = self.update_pool(context, pool, pool, False)
        self.driver._hm_db_delete(context, health_monitor['id'], pool_id)



class WisegridRestclient2_0(WiseClientBase):
    path_keygen = 'rest/keygen'+data_style

    path_pool = 'rest/slb_pool'      # operate pool; 

    path_vserver = 'rest/slb_vserver' # operate vip;
    
    path_rserver = 'rest/slb_rserver' # operate rserver
		
    path_healthcheck = 'rest/healthcheck'   # operate healthmonitor

#    path_schedule = 'rest/sched'   #why use rest/slb_schedule/ping??
    
    def __init__(self,driver, host='192.168.10.50',port='10443'):
        super(WisegridRestclient1_0, self).__init__(host, port)
        self.driver = driver
        self._get_tokenkey()
        
    def _get_tokenkey(self):
        '''get the wisegrid token'''

        uri = self.path_keygen
        res =  self._do_request_read('GET',uri,"" )
        data = res
        if data.has_key('key'):            
            self.token = data['key']
            print "validate success , token is :%s"%self.token
        else:
            raise Exception("Wisegrid lbaas keygen fail!!!!")
    
    def _update_status(self,context,model_type,model_id,reps):
        pass
    def create_pool(self,context,pool):
        pass
  
    def update_pool(self,context,old_pool,pool,member=None):
        
        pass
        
    def delete_pool(self,context,pool):
        
        pass
    def create_vip(self,context,vip):
        pass

    def update_vip(self,context,old_vip,vip):
        pass
        
    def delete_vip(self,context,vip):
        pass
    
    def _create_wisegrid_pool_(self,context,pool_id,pool=None,heathmonitor=None):
        pass
        
    def create_member(self,context,member):
        pass
    
    def update_member(self,context,old_member,member):
        pass
    def delete_member(self,context,member):
        pass
    
    def create_pool_health_monitor(self,context,health_monitor,pool_id):
        pass
        
    def update_pool_health_monitor(self,context,old_health_monitor,health_monitor,pool_id):
        pass
    

if __name__ == "__main__":
    host = "192.168.10.50"
    port = "10443"
    wiseclient = WisegridRestclient1_0(host,port)
    params={"pool":{
            "name":'test_wisegrid_pool_from_openstack',
            "type":"ipv4",
            "healthcheck":"ping",
            "realServer":[]
        }}
    rep = wiseclient.create_pool(params)
    print rep

