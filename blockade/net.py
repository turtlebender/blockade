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

import random
import string

from .errors import BlockadeError
import collections


class NetworkState(object):
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    FLAKY = "FLAKY"
    UNKNOWN = "UNKNOWN"

NetworkController = collections.namedtuple(
  'NetworkController',
  [
    'iptables_call_output',
    'iptables_call',
    'traffic_control_restore',
    'traffic_control_netem',
    'network_state'
  ]
)


class BlockadeNetwork(object):
    def __init__(self, controller, config):
        self.config = config
        self.controller = controller

    def new_veth_device_name(self):
        chars = string.ascii_letters + string.digits
        return "veth" + "".join(random.choice(chars) for _ in range(8))

    def network_state(self, device):
        return self.controller.network_state(device)

    def flaky(self, device):
        flaky_config = self.config.network['flaky'].split()
        self.controller.traffic_control_netem(device, ["loss"] + flaky_config)

    def slow(self, device):
        slow_config = self.config.network['slow'].split()
        self.controller.traffic_control_netem(device, ["delay"] + slow_config)

    def fast(self, device):
        self.controller.traffic_control_restore(device)

    def restore(self, blockade_id):
        clear_iptables(self.controller, blockade_id)

    def partition_containers(self, blockade_id, partitions):
        clear_iptables(self.controller, blockade_id)
        partition_containers(self.controller, blockade_id, partitions)

    def get_ip_partitions(self, blockade_id):
        return iptables_get_source_chains(self.controller, blockade_id)


def parse_partition_index(blockade_id, chain):
    prefix = "%s-p" % (blockade_id,)
    if chain and chain.startswith(prefix):
        try:
            return int(chain[len(prefix):])
        except ValueError:
            pass
    raise ValueError("chain %s is not a blockade partition" % (chain,))


def partition_chain_name(blockade_id, partition_index):
    return "%s-p%s" % (blockade_id, partition_index)


def iptables_get_chain_rules(controller, chain):
    if not chain:
        raise ValueError("invalid chain")
    lines = controller.iptables_call_output("-L", chain)
    if len(lines) < 2:
        raise BlockadeError("Can't understand iptables output: \n%s" %
                            "\n".join(lines))

    chain_line, header_line = lines[:2]
    if not (chain_line.startswith("Chain " + chain) and
            header_line.startswith("target")):
        raise BlockadeError("Can't understand iptables output: \n%s" %
                            "\n".join(lines))
    return lines[2:]


def iptables_get_source_chains(controller, blockade_id):
    """Get a map of blockade chains IDs -> list of IPs targeted at them

    For figuring out which container is in which partition
    """
    result = {}
    if not blockade_id:
        raise ValueError("invalid blockade_id")
    lines = iptables_get_chain_rules(controller, "FORWARD")

    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            partition_index = parse_partition_index(blockade_id, parts[0])
        except ValueError:
            continue  # not a rule targetting a blockade chain

        source = parts[3]
        if source:
            result[source] = partition_index
    return result


def iptables_delete_rules(controller, chain, predicate):
    if not chain:
        raise ValueError("invalid chain")
    if not isinstance(predicate, collections.Callable):
        raise ValueError("invalid predicate")

    lines = iptables_get_chain_rules(controller, chain)

    # TODO this is susceptible to check-then-act races.
    # better to ultimately switch to python-iptables if it becomes less buggy
    for index, line in reversed(list(enumerate(lines, 1))):
        line = line.strip()
        if line and predicate(line):
            controller.iptables_call("-D", chain, str(index))


def iptables_delete_blockade_rules(controller, blockade_id):
    def predicate(rule):
        target = rule.split()[0]
        try:
            parse_partition_index(blockade_id, target)
        except ValueError:
            return False
        return True
    iptables_delete_rules(controller, "FORWARD", predicate)


def iptables_delete_blockade_chains(controller, blockade_id):
    if not blockade_id:
        raise ValueError("invalid blockade_id")

    lines = controller.iptables_call_output("-L")
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "Chain":
            chain = parts[1]
            try:
                parse_partition_index(blockade_id, chain)
            except ValueError:
                continue
            # if we are a valid blockade chain, flush and delete
            controller.iptables_call("-F", chain)
            controller.iptables_call("-X", chain)


def iptables_insert_rule(controller, chain, src=None, dest=None, target=None):
    """Insert a new rule in the chain
    """
    if not chain:
        raise ValueError("Invalid chain")
    if not target:
        raise ValueError("Invalid target")
    if not (src or dest):
        raise ValueError("Need src, dest, or both")

    args = ["-I", chain]
    if src:
        args += ["-s", src]
    if dest:
        args += ["-d", dest]
    args += ["-j", target]
    controller.iptables_call(*args)


def iptables_create_chain(controller, chain):
    """Create a new chain
    """
    if not chain:
        raise ValueError("Invalid chain")
    controller.iptables_call("-N", chain)


def clear_iptables(controller, blockade_id):
    """Remove all iptables rules and chains related to this blockade
    """
    # first remove refererences to our custom chains
    iptables_delete_blockade_rules(controller, blockade_id)

    # then remove the chains themselves
    iptables_delete_blockade_chains(controller, blockade_id)


def partition_containers(controller, blockade_id, partitions):
    if not partitions or len(partitions) == 1:
        return
    for index, partition in enumerate(partitions, 1):
        chain_name = partition_chain_name(blockade_id, index)

        # create chain for partition and block traffic TO any other partition
        iptables_create_chain(controller, chain_name)
        for other in partitions:
            if partition is other:
                continue
            for container in other:
                if container.ip_address:
                    iptables_insert_rule(controller, chain_name, dest=container.ip_address,
                                         target="DROP")

        # direct traffic FROM any container in the partition to the new chain
        for container in partition:
            iptables_insert_rule(controller, "FORWARD", src=container.ip_address,
                                 target=chain_name)
