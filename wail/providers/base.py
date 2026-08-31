class BaseAdapter:

    def __init__(self, client):
        self.client = client

    def invoke(self, *args, **kwargs):
        raise NotImplementedError
