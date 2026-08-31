
def sync(client, payload):
    return client.responses._original_create(**payload)


def stream(client, payload):
    return client.responses._original_stream(**payload)


