#
#  Copyright (C) 2014 Dell, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Helpers for interacting with dvm. This will create a ssh-config file and
# make sure that tc is installed.

import os
import os.path
import subprocess

import blockade.ssh
import blockade.net

import paramiko


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

    config = paramiko.SSHConfig()
    config.parse(open(os.path.expanduser('~/.blockade/ssh-config')))
    dvm = config.lookup('dvm')
    client = blockade.ssh.ssh_init(dvm['hostname'], dvm['user'], dvm['identityfile'][0], dvm['port'])
    stderr = ''
    try:
        _, _, stderr = client.exec_command("which tc > /dev/null || tce-load -wi iproute2")
    except paramiko.SSHException:
        raise blockade.ssh.BlockadeError("Unable to install iproute2 on dvm instance: {0}".format(stderr))
    return {
        'host': dvm['hostname'],
        'user': dvm['user'],
        'key_filename': dvm['identityfile'][0],
        'port': int(dvm['port'])
    }

