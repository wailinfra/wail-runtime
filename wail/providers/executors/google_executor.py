def sync(client, payload):
    return client.models._wail_original_generate_content(**payload)


def stream(client, payload):
    return client.models._wail_original_generate_content_stream(**payload)
