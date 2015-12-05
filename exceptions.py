

from neutron.common import exceptions

class WisegridLBaasException(exceptions.NeutronException):
    message = _('An unknown exception occurred in Wisegrid LBaaS provider.')
    
class AuthenticationMissing(WisegridLBaasException):
    message = _('user/password missing. '
                'Specify in configuration file, under [wisegrid] section')

class UnsupportOperation(WisegridLBaasException):
    message = _('%(operation)s operation is not supported.')             
              
 