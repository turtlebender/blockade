# Helpers for interacting with dvm. This will create a ssh-config file and
# make sure that tc is installed.

import os
import os.path
import subprocess

import blockade.ssh


def dvm_init():
    if not os.path.exists(os.path.expanduser('~/.blockade')):
        os.mkdir(os.path.expanduser('~/.blockade'))

    current_dir = os.getcwd()
    os.chdir(os.path.expanduser('~/.dvm'))
    p = subprocess.Popen(['vagrant', 'ssh-config'], stdout=subprocess.PIPE)
    config = p.communicate()[0]
    with open(os.path.expanduser('~/.blockade/ssh-config'), 'w') as fh:
        fh.write(config)

    os.chdir(current_dir)

    config = SSHConfig()
    config.parse(open(os.path.expanduser('~/.blockade/ssh-config')))
    dvm = config.lookup('dvm')
    client = blockade.ssh.ssh_init(dvm['hostname'], dvm['user'], dvm['identityfile'][0], dvm['port'])
    stderr = ''
    try:
        _, _, stderr = client.exec_command("which tc > /dev/null || tce-load -wi iproute2")
    except SSHException:
        raise BlockadeError("Unable to install iproute2 on dvm instance: {0}".format(stderr))
    return client
