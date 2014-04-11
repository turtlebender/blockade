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

import sys
import argparse
import traceback
import errno
import json

import yaml
from clint.textui import puts, puts_err, colored, columns

from .errors import BlockadeError
from .core import Blockade
from .state import BlockadeStateFactory
from .config import BlockadeConfig
from .net import BlockadeNetwork


def load_config(opts):
    error = None
    paths = (opts.config,) if opts.config else ("blockade.yaml",
                                                "blockade.yml")
    try:
        for path in paths:
            try:
                with open(path) as f:
                    d = yaml.safe_load(f)
                    return BlockadeConfig.from_dict(d)
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise
    except Exception as e:
        error = e
    raise BlockadeError("Failed to load config (from --config, "
                        "./blockade.yaml, or ./blockade.yml)" +
                        (str(error) if error else ""))


def get_blockade(config):
    return Blockade(config, BlockadeStateFactory)


def print_containers(containers, to_json=False):
    containers = sorted(containers, key=lambda c: c.name)

    if to_json:
        d = [c.to_dict() for c in containers]
        puts(json.dumps(d, indent=2, sort_keys=True, separators=(',', ': ')))

    else:
        puts(colored.blue(columns(["NODE",               15],
                                  ["CONTAINER ID",       15],
                                  ["STATUS",              7],
                                  ["IP",                 15],
                                  ["NETWORK",            10],
                                  ["PARTITION",          10])))
        for container in containers:
            partition = container.partition
            partition = "" if partition is None else str(partition)
            puts(columns([container.name,                15],
                         [container.container_id[:12],   15],
                         [container.state,                7],
                         [container.ip_address or "",    15],
                         [container.network_state,       10],
                         [partition,                     10]))


def _add_output_options(parser):
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')


def _add_container_selection_options(parser):
    parser.add_argument('containers', metavar='CONTAINER', nargs='*',
                        help='Container to select')
    parser.add_argument('--all', action='store_true',
                        help='Select all containers')

def _check_container_selections(opts):
    if opts.containers and opts.all:
        raise BlockadeError("Either specify individual containers "
                            "or --all, but not both")
    elif not (opts.containers or opts.all):
        raise BlockadeError("Specify individual containers or --all")

    return (opts.containers or None, opts.all)


def cmd_up(opts):
    """Start the containers and link them together
    """
    config = load_config(opts)
    b = get_blockade(config)
    containers = b.create()
    print_containers(containers, opts.json)


def cmd_destroy(opts):
    """Destroy all containers and restore networks
    """
    config = load_config(opts)
    b = get_blockade(config)
    b.destroy()


def cmd_status(opts):
    """Print status of containers and networks
    """
    config = load_config(opts)
    b = get_blockade(config)
    containers = b.status()
    print_containers(containers, opts.json)


def cmd_flaky(opts):
    """Make the network flaky for some or all containers
    """
    containers, select_all = _check_container_selections(opts)
    config = load_config(opts)
    b = get_blockade(config)
    b.flaky(containers, select_all)


def cmd_slow(opts):
    """Make the network slow for some or all containers
    """
    containers, select_all = _check_container_selections(opts)
    config = load_config(opts)
    b = get_blockade(config)
    b.slow(containers, select_all)


def cmd_fast(opts):
    """Restore network speed and reliability for some or all containers
    """
    containers, select_all = _check_container_selections(opts)
    config = load_config(opts)
    b = get_blockade(config)
    b.fast(containers, select_all)


def cmd_partition(opts):
    """Partition the network between containers

    Replaces any existing partitions outright. Any containers NOT specified
    in arguments will be globbed into a single implicit partition. For
    example if you have three containers: c1, c2, and c3 and you run:

        blockade partition c1

    The result will be a partition with just c1 and another partition with
    c2 and c3.
    """
    partitions = []
    for partition in opts.partitions:
        names = []
        for name in partition.split(","):
            name = name.strip()
            if name:
                names.append(name)
        partitions.append(names)
    config = load_config(opts)
    b = get_blockade(config)
    b.partition(partitions)


def cmd_join(opts):
    """Restore full networking between containers
    """
    config = load_config(opts)
    b = get_blockade(config)
    b.join()


def cmd_logs(opts):
    """Fetch the logs of a container
    """
    config = load_config(opts)
    b = get_blockade(config)
    puts(b.logs(opts.container))


_CMDS = (("up", cmd_up), ("destroy", cmd_destroy), ("status", cmd_status),
         ("logs", cmd_logs), ("flaky", cmd_flaky), ("slow", cmd_slow),
         ("fast", cmd_fast), ("partition", cmd_partition), ("join", cmd_join))


def setup_parser():
    parser = argparse.ArgumentParser(description='Blockade')
    parser.add_argument("--config", "-c", metavar="blockade.yaml",
                        help="Config YAML. Looks in CWD if not specified.")

    subparsers = parser.add_subparsers(title="commands")

    command_parsers = {}
    for command, func in _CMDS:
        subparser = subparsers.add_parser(
            command,
            description=func.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
        subparser.set_defaults(func=func)
        command_parsers[command] = subparser

    # add additional parameters to some commands
    _add_output_options(command_parsers["up"])
    _add_output_options(command_parsers["status"])
    _add_container_selection_options(command_parsers["flaky"])
    _add_container_selection_options(command_parsers["slow"])
    _add_container_selection_options(command_parsers["fast"])

    command_parsers["logs"].add_argument("container", metavar='CONTAINER',
                                         help="Container to fetch logs for")
    command_parsers["partition"].add_argument(
        'partitions', nargs='+', metavar='PARTITION',
        help='Comma-separated partition')

    return parser


def main(args=None):
    parser = setup_parser()
    opts = parser.parse_args(args=args)

    rc = 0

    try:
        opts.func(opts)
    except BlockadeError as e:
        puts_err(colored.red("\nError:\n") + str(e) + "\n")
        rc = 1

    except KeyboardInterrupt:
        puts_err(colored.red("Caught Ctrl-C. exiting!"))

    except:
        puts_err(
            colored.red("\nUnexpected error! This may be a Blockade bug.\n"))
        traceback.print_exc()
        rc = 2

    sys.exit(rc)


if __name__ == '__main__':
    main()
