"""Shared audio device label helpers for tray UI and notifications."""


def get_active_device_status(daemon_inst):
    """
    Returns display strings for the current default output and input.

    output_label includes volume when available (e.g. 'Built-in Audio · 42%').
    Returns: (sink_desc, source_desc, output_label, vol_val)
    """
    current_sink = daemon_inst.get_default_sink()
    current_source = daemon_inst.get_default_source()
    sinks = daemon_inst.query_sinks()
    sources = daemon_inst.query_sources()

    sink_desc = next(
        (s.get("description", current_sink) for s in sinks if s["name"] == current_sink),
        current_sink,
    )
    source_desc = next(
        (s.get("description", current_source) for s in sources if s["name"] == current_source),
        current_source,
    )

    output_label = sink_desc
    vol_val = 0
    for s in sinks:
        if s["name"] != current_sink:
            continue
        vol_dict = s.get("volume", {})
        if not vol_dict:
            break
        first_channel = list(vol_dict.values())[0]
        val_pct = first_channel.get("value_percent", "")
        if val_pct:
            output_label = f"{sink_desc} · {val_pct}"
            try:
                vol_val = int(val_pct.strip("%"))
            except ValueError:
                vol_val = 0
        break

    return sink_desc, source_desc, output_label, vol_val


def get_tooltip_strings(daemon_inst):
    """Returns (title, subtitle) for SNI ToolTip and panel hover text."""
    _, source_desc, output_label, _ = get_active_device_status(daemon_inst)
    return output_label, f"Input: {source_desc}"
