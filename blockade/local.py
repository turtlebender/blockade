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

import subprocess

from .errors import BlockadeError
from .net import NetworkState, NetworkController

def init_local_network_controller():
    def iptables_call_output(*args):
        cmd = ["iptables", "-n"] + list(args)
        try:
            output = subprocess.check_output(cmd)
            return output.decode().split("\n")
        except subprocess.CalledProcessError:
            raise BlockadeError("Problem calling '%s'" % " ".join(cmd))

    def iptables_call(*args):
        cmd = ["iptables"] + list(args)
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            raise BlockadeError("Problem calling '%s'" % " ".join(cmd))

    def traffic_control_restore(device):
        cmd = ["tc", "qdisc", "del", "dev", device, "root"]

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        _, stderr = p.communicate()
        stderr = stderr.decode()

        if p.returncode != 0:
            if p.returncode == 2 and stderr:
                if "No such file or directory" in stderr:
                    return

            # TODO log error somewhere?
            raise BlockadeError("Problem calling traffic control: " +
                                " ".join(cmd))

    def traffic_control_netem(device, params):
        cmd = ["tc", "qdisc", "replace", "dev", device,
               "root", "netem"] + params
        try:
            subprocess.check_call(cmd)

        except subprocess.CalledProcessError:
            # TODO log error somewhere?
            raise BlockadeError("Problem calling traffic control: " +
                                " ".join(cmd))

    def network_state(device):
        try:
            output = subprocess.check_output(
                ["tc", "qdisc", "show", "dev", device]).decode()
            # sloppy but good enough for now
            if " delay " in output:
                return NetworkState.SLOW
            if " loss " in output:
                return NetworkState.FLAKY
            return NetworkState.NORMAL

        except subprocess.CalledProcessError:
            # TODO log error somewhere?
            return NetworkState.UNKNOWN

    return NetworkController(
        iptables_call_output,
        iptables_call,
        traffic_control_restore,
        traffic_control_netem,
        network_state
    )
