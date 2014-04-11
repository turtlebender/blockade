from fabric.api import *

env.use_ssh_config = True
env.ssh_config_path = "/Users/trhowe/.dvm/ssh-config"
env.disable_known_hosts = True
env.shell = "/bin/ash -l -c"

def test():
    sudo('ls /tmp')

execute(test, hosts=['dvm'])
