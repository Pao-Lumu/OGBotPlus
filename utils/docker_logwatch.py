import sys

import docker
from docker.models.containers import Container

dock = docker.from_env()


def wait_or_when_cancelled(id):
    con: Container = dock.containers.get(id)
    log = con.attach(stdout=True, stream=True, logs=False)
    while True:
        print(log.next())


wait_or_when_cancelled(sys.argv[1])
