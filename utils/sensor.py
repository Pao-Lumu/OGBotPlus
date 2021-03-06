import csv
import logging
import os
import re
from os import path
from pathlib import Path
from typing import Dict, Tuple, List, Union

import psutil
import toml
from docker import DockerClient
from docker.models.containers import Container

docker_client = DockerClient(base_url='unix://var/run/docker.sock', tls=True, version="auto")


def are_servers_running(ports: List[int]) -> bool:
    for p in psutil.process_iter(attrs=['connections']):
        if not p.info['connections']:
            continue
        for x in p.info['connections']:
            if x.laddr.port in ports:
                return True
    else:
        # print('hmm')
        if len(docker_client.containers.list(filters={'status': 'running'})) > 0:
            return True
    return False


def get_running_servers(ports: List[int]) -> List[Tuple[int, Union[psutil.Process, Container]]]:
    # print("get_running_servers")
    running_servers = []
    used_ports = []
    result = docker_client.containers.list(filters={'status': 'running'}, all=True)
    logging.debug(ports)

    # bare-metal processes
    for p in psutil.process_iter():
        try:
            if not p.connections(kind='inet4'):
                continue
            connections = [y.laddr.port for y in p.connections(kind='inet4')]
        except psutil.AccessDenied:
            continue
        connections.sort()
        for x in connections:
            logging.debug(x)
            if x in ports and p not in used_ports:
                running_servers.append((x, p))
                used_ports.append(p)
    logging.debug(running_servers)

    # docker containers
    for container in result:
        for con_port, host_info in container.ports.items():
            logging.debug("host_info")
            logging.debug(host_info)

            # asdf = [conn['HostPort'] for conn in host_info if host_info]
            # logging.debug(asdf in ports)
            # logging.debug(int(asdf[0]) in ports)

            logging.debug([conn['HostPort'] for conn in host_info if int(conn['HostPort'])])
            if host_info:
                running_servers.extend([(conn['HostPort'], container) for conn in host_info if
                                        int(conn['HostPort']) in ports
                                        and ':' not in conn['HostIp']
                                        and 'tcp' in con_port])
                logging.debug(f"Key: {con_port}; Value: {host_info}")
            else:
                logging.debug(con_port)
    logging.debug("running_servers")
    logging.debug(running_servers)
    return running_servers


def get_running_procs(ports: List[int]) -> List[Tuple[int, Union[psutil.Process, str]]]:
    running_procs = []
    temp = []
    for p in psutil.process_iter(attrs=['connections']):
        if not p.info['connections']:
            continue
        connections = [y.laddr.port for y in p.info['connections']]
        connections.sort()
        for x in connections:
            if x in ports and p not in temp:
                running_procs.append((x, p))
                temp.append(p)
    return running_procs


def get_running_containers(ports: List[int]):
    result = docker_client.containers.list(filters={'status': 'running'}, all=True)
    running_cons = []
    for container in result:
        for _, v in container.ports.items():
            if v['HostPort'] in ports:
                running_cons.append(container)
                break
            continue
    return running_cons


def is_lgsm(proc: psutil.Process) -> bool:
    return True if "serverfiles" in str(proc.cwd()) else False


def find_root_directory(start_dir: str) -> str:
    if not os.path.isdir(start_dir):
        raise FileNotFoundError(start_dir + "is either not a valid directory path or not accessible")
    else:
        parent = start_dir
        looking_for_root = True
        while looking_for_root:
            parent, current = path.split(parent)
            if "serverfiles" in parent:  # if using LGSM, move up until you're in the top folder, if using MC, ignore
                continue
            elif "serverfiles" not in parent and "serverfiles" in current:  # if already in top folder or running MC return parent
                looking_for_root = False
                return parent
            elif "serverfiles" not in parent:
                return os.path.join(parent, current)
            else:
                print("Hey... This isn't supposed to happen...")


def get_game_info(process: Union[psutil.Process, Container]) -> Dict:
    # print('get_game_info')
    if isinstance(process, psutil.Process):
        try:
            cwd = process.cwd()
            root = find_root_directory(cwd)
            toml_path = path.join(root, '.gameinfo.toml')

            defaults = {'name': Path(root).name,
                        'game': '',
                        'folder': cwd,
                        'rcon': '',
                        'executable': process.name(),
                        'command': process.cmdline()}
        except ProcessLookupError:
            raise ProcessLookupError('Process not running or not accessible by bot.')
        if is_lgsm(process):
            game_name = ""
            with os.scandir(root) as scan:
                for f in scan:
                    if f.name.endswith('server'):
                        game_name = f.name
                        break
            # define paths to noteworthy places
            root_dir = root
            log_dir = path.join(root_dir, 'log')
            server_files = path.join(root_dir, 'serverfiles')
            lgsm_dir = path.join(root_dir, 'lgsm')
            config_dir = path.join(lgsm_dir, 'config-lgsm', game_name)
            readable_name = ''
            try:
                with open(path.join(config_dir, f'{game_name}.cfg')) as f:
                    game_cfg = toml.load(f)
            except toml.TomlDecodeError as e:
                print("File failed to parse.")
                print(e)
                print(e.mro())
            with open(path.join(lgsm_dir, 'data', 'serverlist.csv')) as svr_names:
                for row in csv.reader(svr_names, csv.unix_dialect):
                    if row[1] == game_name:
                        readable_name = row[2]
                        break

            defaults = {'name': readable_name,
                        'game': game_name,
                        'folder': root_dir,
                        'logs': log_dir,
                        'configs': config_dir,
                        'server_files': server_files,
                        # This list comprehension is really annoying and probably pointless.
                        'rcon_password': [v if re.match("rcon.?pa", k, re.I) else '' for k, v in game_cfg.items()][0],
                        'launch_script': path.join(root_dir, game_name),
                        'executable': process.name(),
                        'command': process.cmdline()}
    elif isinstance(process, Container):
        # print(process)
        root = Path(process.labels['com.docker.compose.project.working_dir'])
        # print(root)
        toml_path = path.join(root, '.gameinfo.toml')
        # print(toml_path)
        try:
            defaults = {'name': Path(root).name,
                        'game': process.labels['com.docker.compose.service'],
                        'folder': process.attrs['Mounts'][0]['Source'],
                        'rcon': '',
                        'executable': process.name,
                        'command': 'docker-compose --compatibility up -d',
                        'compose_folder': root}
        except Exception as e:
            print(type(e))
            print(e)
            raise RuntimeError
    else:
        raise RuntimeError('get_game_info was passed an object that was not a Process or a Container')

    # if the TOML file exists, load then override the defaults, and save
    # this should correctly add new fields when they are programmed in.
    if os.path.isfile(toml_path):
        # print('is file')
        try:
            with open(toml_path) as file:

                game_info = {**defaults, **toml.load(file)}

            with open(toml_path, "w") as file:
                toml.dump(game_info, file)

        except toml.TomlDecodeError as e:
            print(f"TOML decoding error | {e}")
            raise toml.TomlDecodeError
        except Exception as e:
            print(f"Exception {type(e)}: {e}")
        return game_info
    else:
        # print('generating file')
        try:
            # if the TOML file doesn't exist, create it, load defaults, and save
            Path(toml_path).touch()
            print(f"created new gameinfo file at {toml_path}")

            with open(toml_path, "w") as file:
                toml.dump(defaults, file)
        except toml.TomlDecodeError as e:
            print(f"TOML decoding error | {e}")
            raise toml.TomlDecodeError
        except Exception as e:
            print(f"Exception {type(e)}: {e}")

        return defaults
