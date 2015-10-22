import sys
import parseconfig
import argparse
import os
import docker


def create_parser():
	parser = argparse.ArgumentParser()
	parser.add_argument("--home", default = os.environ["HOME"])

	return parser


parser = create_parser()
namespace = parser.parse_args(sys.argv[1:])
# print(namespace.home)

config = parseconfig.conf_dict("config.json")

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
			port_bind[port[0]] = None
	links = []
	for link in cont["env"]["dependent"]:
		links.append((link, link))
	if cont["image"]["ExtRepo"]:
		container_id = docker_client.create_container(image = cont["image"]["RepoTag"], name = cont["name"], volumes = vol_point,
													  host_config = docker.utils.create_host_config(binds = binds, port_bindings = port_bind,
																									links = links), environment = cont["env"]["vars"],
													  ports = ports)
		docker_client.start(container_id)


def starter(cont):
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
				# TODO Запустить билд образа, указав имя_папки_image в качестве repo:tag
				pass
			else:
				raise Exception("path error")


for key, c in config["containers"].items():
	starter(c)
