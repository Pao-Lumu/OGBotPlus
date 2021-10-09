import csv
import os
import re
from os import path
from pathlib import Path
from subprocess import PIPE, DEVNULL
from typing import Dict, Tuple, List, Union

import psutil
import toml


def are_servers_running(ports: List[int]) -> bool:
    for p in psutil.process_iter(attrs=['connections']):
        if not p.info['connections']:
            continue
        for x in p.info['connections']:
            if x.laddr.port in ports:
                return True
    else:
        return False


def get_running_procs(ports: List[int]) -> List[Tuple[int, psutil.Process]]:
    running_procs = []
    for p in psutil.process_iter(attrs=['connections']):
        if not p.info['connections']:
            continue
        connections = [y.laddr.port for y in p.info['connections']]
        connections.sort()
        for x in connections:
            if x in ports and p not in [p for _, p in running_procs]:
                running_procs.append((x.laddr.port, p))
    return running_procs


def is_lgsm(proc: psutil.Process) -> bool:
    return True if "serverfiles" in str(proc.cwd()) else False


def find_root_directory(start_dir: str) -> str:
    if not os.path.isdir(start_dir):
        print(start_dir)
        raise FileNotFoundError(start_dir + "is either not a valid directory path or not accessible")
    else:
        # print("starting to search")
        parent = start_dir
        looking_for_root = True
        while looking_for_root:
            parent, current = path.split(parent)
            if "serverfiles" in parent:  # if using LGSM, move up until you're in the top folder, if using MC, ignore
                continue
            elif "serverfiles" not in parent and "serverfiles" in current:  # if already in top folder or running MC return parent
                looking_for_root = False
                # print("found/defaulted")
                return parent
            elif "serverfiles" not in parent:
                return os.path.join(parent, current)
            else:
                print("Hey... This isn't supposed to happen...")


def get_game_info(process: psutil.Process) -> Dict:
    try:
        cwd = process.cwd()
    except ProcessLookupError:
        raise ProcessLookupError('Process not running or not accessible by bot.')
    root = find_root_directory(cwd)
    toml_path = path.join(root, '.gameinfo.toml')
    defaults = {'name': Path(root).name,
                'game': '',
                'folder': cwd,
                'rcon': '',
                'executable': process.name(),
                'command': process.cmdline()}
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
    # if the TOML file exists, load then override the defaults, and save
    # this should correctly add new fields when they are programmed in.
    if os.path.isfile(toml_path):
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
        try:
            # if the TOML file doesn't exist, create it, load defaults, and save
            Path(toml_path).touch()
            print(f"created new gameinfo file at {cwd}")

            with open(toml_path, "w") as file:
                toml.dump(defaults, file)
        except toml.TomlDecodeError as e:
            print(f"TOML decoding error | {e}")
            raise toml.TomlDecodeError
        except Exception as e:
            print(f"Exception {type(e)}: {e}")

        return defaults
