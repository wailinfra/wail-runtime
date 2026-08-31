def on_inference_start(emit_event):
    emit_event("inference_started")


def on_inference_end(emit_event):
    emit_event("inference_finished")
