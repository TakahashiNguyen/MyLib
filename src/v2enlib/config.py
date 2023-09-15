import yaml


class Config:
    def __init__(self, key=None, value=None) -> None:
        if key is None and value is None:
            with open("config.yml") as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
                Config.create_subclass(self, "", config)
        else:
            Config.create_subclass(self, key, value)

    @staticmethod
    def create_subclass(self, key: str, values: any):
        if isinstance(values, dict):
            for key, value in values.items():
                if isinstance(value, dict):
                    Config.create_subclass(self, key, Config(key, value))
                else:
                    Config.create_subclass(self, key, value)
        else:
            setattr(self, key, values)


config = Config()
