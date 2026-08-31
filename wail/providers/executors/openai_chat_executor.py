def sync(client, payload):

    return client.chat.completions.create(**payload)


def stream(client, payload):

    payload = payload.copy()
    payload["stream"] = True

    return client.chat.completions.create(**payload)