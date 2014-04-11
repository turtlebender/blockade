import logging
import paramiko, base64
from binascii import hexlify
import socket

logging.basicConfig()

def agent_auth(transport, username):
    """
    Attempt to authenticate to the given transport using any of the private
    keys available from an SSH agent.
    """
    
    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    if len(agent_keys) == 0:
        return
        
    for key in agent_keys:
        print 'Trying ssh-agent key %s' % hexlify(key.get_fingerprint()),
        try:
            transport.auth_publickey(username, key)
            print '... success!'
            return
        except paramiko.SSHException:
            print '... nope.'

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.WarningPolicy())
key = paramiko.RSAKey.from_private_key_file("vagrant.key")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 2200))
t = paramiko.Transport(sock)
t.start_client()
agent_auth(t, "docker")
chan = t.open_session()
chan.get_pty()
chan.invoke_shell()
print '*** Here we go!'
print
interactive.interactive_shell(chan)
chan.close()
t.close()

