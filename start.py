import sys
import parseconfig
import argparse
import os
import docker
import json
from io import BytesIO


def create_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument("--home", default = os.environ["HOME"])
	parser.add_argument("--conf", default = "config.json")

	return parser


parser = create_parser()
namespace = parser.parse_args(sys.argv[1:])

config = parseconfig.conf_dict(namespace.conf)

root_folder = namespace.home + "/" + config["folder"]
os.chdir(root_folder)

docker_client = docker.Client(base_url = "unix://var/run/docker.sock")


def is_exist_container(cont_name, status):
	if status is not None:
		containers = docker_client.containers(all = True, filters = {"status": status})
	else:
		containers = docker_client.containers(all = True)
	for c in containers:
		for name in c["Names"]:
			if cont_name == name:
				return True
	return False


def id_container(cont_name, status):
	if status is not None:
		containers = docker_client.containers(all = True, filters = {"status": status})
	else:
		containers = docker_client.containers(all = True)
	for c in containers:
		for name in c["Names"]:
			if cont_name == name:
				return c["Id"]
	return False


def is_exist_image(repotag):
	for c in docker_client.images(all = True):
		for rt in c["RepoTags"]:
			if repotag == rt:
				return True
	return False


def run_container(cont):
	vol_point = []
	binds = {}
	for vol in cont["env"]["volumes"]:
		host_folder = root_folder + "/" + vol[0]
		vol_point.append(vol[1])
		binds[host_folder] = {
			"bind": vol[1],
			"mode": "rw"
		}
	ports = []
	port_bind = {}
	for port in cont["env"]["ports"]:
		ports.append(port[0])
		if len(port) == 2:
			port_bind[port[0]] = port[1]
		elif len(port) == 1:
			pass
	links = []
	for link in cont["env"]["dependent"]:
		links.append((link, link))
	if not is_exist_image(cont["image"]["RepoTag"]):
		repo, tag = cont["image"]["RepoTag"].split(":")
		for line in docker_client.pull(repository = repo, tag = tag, stream = True):
			print(json.dumps(json.loads(line.decode('utf-8')), indent = 4).encode("utf-8"))

	container_id = docker_client.create_container(image = cont["image"]["RepoTag"], name = cont["name"], volumes = vol_point, ports = ports,
												  host_config = docker.utils.create_host_config(binds = binds, port_bindings = port_bind,
																								links = links), environment = cont["env"]["vars"])
	docker_client.start(container_id)


def build_container(cont):
	df = open(cont["folder"] + "/Dockerfile", "r")
	dockerfile = df.read()
	f = BytesIO(dockerfile.encode('utf-8'))
	response = []
	for line in docker_client.build(fileobj = f, dockerfile = "./Dockerfile", rm = True, tag = cont["image"]["RepoTag"]):
		print(json.dumps(json.loads(line.decode('utf-8')), indent = 4).encode("utf-8"))
		response.append(line)
	return response


def starter(cont):
	if "ignore" in cont and cont["ignore"]:
		return
	if len(cont["env"]["dependent"]):
		for depend in cont["env"]["dependent"]:
			starter(config["containers"][depend])
	name_for_search = "/" + cont["name"]
	if is_exist_container(name_for_search, "running"):
		return
	elif is_exist_container(name_for_search, None):
		id = id_container(name_for_search, None)
		docker_client.start(container = id)
		return
	else:
		if is_exist_image(cont["image"]["RepoTag"]) or cont["image"]["ExtRepo"]:
			run_container(cont)
		else:
			contaner_path = root_folder + "/{0}".format(cont["name"])
			if os.path.exists(contaner_path) and os.path.exists(contaner_path + "/Dockerfile"):
				build_container(cont)
				run_container(cont)
			else:
				raise Exception("path error")


for key, c in config["containers"].items():
	starter(c)
