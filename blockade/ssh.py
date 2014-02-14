# Support for executing network commands over ssh.

import paramiko
from paramiko import SSHException, SSHClient, SSHConfig, util, RSAKey

def ssh_init(host, user, private_key_file, port=22):
    client=SSHClient()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    rsa_key = RSAKey.from_private_key_file(private_key_file)
    client.connect(host, int(port), username=user, pkey=rsa_key)
    return client


class SSHExecutor(object):
    def __init__(self, client):
        self.client = client

    def iptables_call_output(*args):
        cmd = ['iptables', '-n'] + list(args)
        cmd = ' '.join(cmd)
        try:
            _, stdout, stderr = self.client.exec_command(cmd)
            return stdout.read().decode().split("\n")
        except SSHException:
            raise BlockadeError("Problem calling {0}".format(cmd))

    def iptables_call(*args):
        cmd = ['iptables'] + list(args)
        cmd = ' '.join(cmd)
        try:
            self.client.exec_command(cmd)
        except SSHException:
            raise BlockadeError("Problem calling {0}".format(cmd))

    def traffic_control_restore(device):
        cmd = "tc qdisc del dev {0} root".format(device)
        stderr = ''
        try:
            _, _, stderr = self.client.exec_command(cmd)
        except SSHException:
            if 'No such file or directory' in stderr.read():
                return
            raise BlockadeError("Problem calling traffic control: {0}".format(cmd))

    def traffic_control_netem(device, params):
        cmd = "tc qdisc replace dev {0} root netem {1}".format(device, params)
        try:
            _, _, stderr = self.client.exec_command(cmd)
        except SSHException:
            return BlockadeError("Problem calling traffic control: {0}".format(cmd))

    def network_state(device):
        try:
            cmd = "tc qdisc show dev {0}".format(device)
            stdout = ''
            _, stdout, _ = self.client.exec_command(cmd)
            if " delay " in output:
                return NetworkState.SLOW
            if " loss " in output:
                return NetworkState.FLAKY
            return NetworkState.NORMAL
        except SSHException:
            return NetworkState.UNKNOWN
