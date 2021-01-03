import json
import os

from src.storage.config import data_path


class DataHelper:
    def __init__(self):
        if not os.path.exists(data_path):
            self.data = {}
        else:
            try:
                with open(data_path, 'r') as data_file:
                    self.data = json.loads(data_file.read())
            except:
                self.data = {}

    def save_file(self):
        with open(data_path, 'w') as data_file:
            data_file.write(json.dumps(self.data, indent=4))

    def reload_file(self):
        try:
            with open(data_path, 'r') as data_file:
                self.data = json.loads(data_file.read())
        except:
            self.data = {}

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save_file()

    def __getitem__(self, item):
        self.reload_file()
        return self.data.get(item, None)

    def get(self, item, default=None):
        value = self.__getitem__(item)
        if default is None:
            return value
        elif value is None:
            return default
        else:
            return value
