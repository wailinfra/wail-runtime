def sync(client, payload):
    return client.messages._original_create(**payload)


def stream(client, payload):
    return client.messages._original_stream(**payload)

