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

# Support for executing network commands over ssh.

import paramiko
from paramiko import SSHException, SSHClient, RSAKey
from .errors import BlockadeError
from .net import NetworkState, NetworkController

def ssh_init(host, user, private_key_file, port=22):
    client=SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    rsa_key = RSAKey.from_private_key_file(private_key_file)
    client.connect(host, int(port), username=user, pkey=rsa_key)
    return client


def ssh_network_controller(hostname, port=22, username=None, password=None, pkey=None,
                           key_filename=None, timeout=None, allow_agent=True, look_for_keys=True, compress=False):
    client = SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port, username, password, pkey, key_filename, timeout, allow_agent, look_for_keys, compress)

    def iptables_call_output(*args):
        cmd = ['sudo', 'iptables', '-n'] + list(args)
        cmd = ' '.join(cmd)
        try:
            _, stdout, stderr = client.exec_command(cmd)
            return stdout.read().decode().split("\n")
        except SSHException:
            raise BlockadeError("Problem calling {0}".format(cmd))

    def iptables_call(*args):
        cmd = ['sudo', 'iptables'] + list(args)
        cmd = ' '.join(cmd)
        try:
            client.exec_command(cmd)
        except SSHException:
            raise BlockadeError("Problem calling {0}".format(cmd))

    def traffic_control_restore(device):
        cmd = "sudo tc qdisc del dev {0} root".format(device)
        stderr = ''
        try:
            _, _, stderr = client.exec_command(cmd)
        except SSHException:
            if 'No such file or directory' in stderr.read():
                return
            raise BlockadeError("Problem calling traffic control: {0}".format(cmd))

    def traffic_control_netem(device, params):
        cmd = "sudo tc qdisc replace dev {0} root netem {1}".format(device, ' '.join(params))
        try:
            _, _, stderr = client.exec_command(cmd)
        except SSHException:
            return BlockadeError("Problem calling traffic control: {0}".format(cmd))

    def network_state(device):
        try:
            cmd = "sudo tc qdisc show dev {0}".format(device)
            _, stdout, _ = client.exec_command(cmd)
            result = stdout.read().decode()
            if " delay " in result:
                return NetworkState.SLOW
            if " loss " in result:
                return NetworkState.FLAKY
            return NetworkState.NORMAL
        except SSHException:
            return NetworkState.UNKNOWN

    return NetworkController(
        iptables_call_output,
        iptables_call,
        traffic_control_restore,
        traffic_control_netem,
        network_state
    )