import json


def conf_dict(file):
	with open(file) as conf_json:
		content_json = json.load(conf_json)
		return content_json
