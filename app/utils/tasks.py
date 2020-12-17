import typing as t
from fastapi.encoders import jsonable_encoder

from tasks import celery_app
from app.db.models.port import Port
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.schemas.server import ServerEdit

from .gost import generate_gost_config, get_gost_remote_ip
from .v2ray import generate_v2ray_config


def send_iptables(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "local_port": port.num,
    }
    if new:
        if new.method == MethodEnum.IPTABLES:
            kwargs["update_status"] = True
            kwargs["remote_ip"] = new.config.get("remote_ip")
            kwargs["remote_port"] = new.config.get("remote_port")
            kwargs["forward_type"] = new.config.get("type", "ALL").upper()
        else:
            # iptables and gost runner will clean iptables rules, so we skip here.
            print(f"Skipping iptables_runner task")
            return
    print(f"Sending iptables_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.iptables.iptables_runner", kwargs=kwargs)


def send_gost(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    gost_config = generate_gost_config(rule)
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "gost_config": gost_config,
        "remote_ip": get_gost_remote_ip(gost_config),
        "update_status": bool(new and new.method == MethodEnum.GOST),
    }
    print(f"Sending gost_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.gost.gost_runner", kwargs=kwargs)


def send_v2ray(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    v2ray_config = generate_v2ray_config(rule)
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "v2ray_config": v2ray_config,
        "update_status": bool(new and new.method == MethodEnum.V2RAY),
    }
    print(f"Sending v2ray_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.v2ray.v2ray_runner", kwargs=kwargs)


def send_brook(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.BROOK),
    }
    if new and new.method == MethodEnum.BROOK:
        kwargs["command"] = new.config.get("command")
        if new.config.get("command") == "relay":
            kwargs["args"] = (
                f"-f :{port.num} "
                f"-t {new.config.get('remote_address')}:{new.config.get('remote_port')}"
            )
        elif new.config.get("command") in ("server", "wsserver"):
            kwargs["args"] = f"-l :{port.num} -p {new.config.get('password')}"
        elif new.config.get("command") in ("client", "wsclient"):
            kwargs["args"] = (
                f"--socks5 0.0.0.0:{port.num} "
                f"-s {new.config.get('remote_address')}:{new.config.get('remote_port')} "
                f"-p {new.config.get('password')}"
            )
        else:
            kwargs["args"] = new.config.get("args")
    print(f"Sending brook_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.brook.brook_runner", kwargs=kwargs)


def send_ehco(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.EHCO),
    }
    if new and new.method == MethodEnum.EHCO:
        transport_type = new.config.get("transport_type", "raw")
        kwargs["args"] = (
            f"-l 0.0.0.0:{port.num} "
            f"--lt {new.config.get('listen_type', 'raw')} "
            f"-r {'wss://' if transport_type.endswith('wss') else ('ws://' if transport_type != 'raw' else '')}"
            f"{new.config.get('remote_address')}:{new.config.get('remote_port')} "
            f"--tt {new.config.get('transport_type', 'raw')}"
        )
    print(f"Sending ehco_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.ehco.ehco_runner", kwargs=kwargs)


def send_socat(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.SOCAT),
    }
    if new and new.method == MethodEnum.SOCAT:
        remote = f'{new.config.get("remote_address")}:{new.config.get("remote_port")}'
        if new.config.get("type") == "UDP":
            kwargs[
                "args"
            ] = f'/bin/sh -c \\"socat UDP4-LISTEN:{port.num},fork,reuseaddr UDP4:{remote}\\"'
        elif new.config.get("type") == "ALL":
            kwargs["args"] = (
                f'/bin/sh -c \\"socat UDP4-LISTEN:{port.num},fork,reuseaddr UDP4:{remote} & '
                f'socat TCP4-LISTEN:{port.num},fork,reuseaddr TCP4:{remote}\\"'
            )
        else:
            kwargs[
                "args"
            ] = f'/bin/sh -c \\"socat TCP4-LISTEN:{port.num},fork,reuseaddr TCP4:{remote}\\"'
    print(f"Sending socat_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.socat.socat_runner", kwargs=kwargs)


def send_node_exporter(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.NODE_EXPORTER),
    }
    print(f"Sending node_exporter_runner task, kwargs: {kwargs}")
    celery_app.send_task(
        "tasks.node_exporter.node_exporter_runner", kwargs=kwargs
    )


def send_wstunnel(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.WSTUNNEL),
    }
    if new and new.method == MethodEnum.WSTUNNEL:
        if new.config.get("client_type") == "client":
            kwargs["args"] = (
                f"{'-u ' if new.config.get('forward_type') == 'UDP' else ''}"
                f"-L 0.0.0.0:{port.num}:127.0.0.1:{new.config.get('proxy_port')} "
                f"{new.config.get('protocol')}://{new.config.get('remote_address')}:{new.config.get('remote_port')} "
            )
        else:
            kwargs["args"] = (
                f"--server "
                f"{new.config.get('protocol')}://0.0.0.0:{port.num} "
                f"-r 127.0.0.1:{new.config.get('proxy_port')} "
            )
    print(f"Sending wstunnel_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.wstunnel.wstunnel_runner", kwargs=kwargs)


def send_tiny_port_mapper(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(
            new and new.method == MethodEnum.TINY_PORT_MAPPER
        ),
    }
    if new and new.method == MethodEnum.TINY_PORT_MAPPER:
        kwargs["args"] = (
            f"-l0.0.0.0:{port.num} "
            f"-r{new.config.get('remote_address')}:{new.config.get('remote_port')} "
            f"{'-t ' if new.config.get('type') == 'ALL' or new.config.get('type') == 'TCP' else ''}"
            f"{'-u ' if new.config.get('type') == 'ALL' or new.config.get('type') == 'UDP' else ''}"
        )
    print(f"Sending tiny_port_mapper_runner task, kwargs: {kwargs}")
    celery_app.send_task(
        "tasks.tiny_port_mapper.tiny_port_mapper_runner", kwargs=kwargs
    )


def send_shadowsocks(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "update_status": bool(new and new.method == MethodEnum.SHADOWSOCKS),
    }
    if new and new.method == MethodEnum.SHADOWSOCKS:
        if new.config.get("encryption") in (
            "AEAD_AES_128_GCM",
            "AEAD_AES_256_GCM",
            "AEAD_CHACHA20_POLY1305",
        ):
            kwargs["version"] = "/usr/local/bin/shadowsocks_go2"
            kwargs["args"] = (
                f" -s 0.0.0.0:{port.num}"
                f" -cipher {new.config.get('encryption')} -password {new.config.get('password')}"
            )
        else:
            kwargs["version"] = "/usr/local/bin/shadowsocks_go"
            kwargs[
                "args"
            ] = f" -p {port.num} -m {new.config.get('encryption')} -k {new.config.get('password')}"
    print(f"Sending shadowsocks_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.shadowsocks.shadowsocks_runner", kwargs=kwargs)


def trigger_forward_rule(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    print(
        f"Received forward rule:\n"
        + f"old:{jsonable_encoder(old) if old else None}\n"
        + f"new:{jsonable_encoder(new) if new else None}"
    )
    if any(r.method == MethodEnum.IPTABLES for r in (old, new) if r):
        send_iptables(rule, port, old, new)

    if any(r.method == MethodEnum.GOST for r in (old, new) if r):
        send_gost(rule, port, old, new)

    if any(r.method == MethodEnum.EHCO for r in (old, new) if r):
        send_ehco(rule, port, old, new)

    if any(r.method == MethodEnum.V2RAY for r in (old, new) if r):
        send_v2ray(rule, port, old, new)

    if any(r.method == MethodEnum.BROOK for r in (old, new) if r):
        send_brook(rule, port, old, new)

    if any(r.method == MethodEnum.SOCAT for r in (old, new) if r):
        send_socat(rule, port, old, new)

    if any(r.method == MethodEnum.WSTUNNEL for r in (old, new) if r):
        send_wstunnel(rule, port, old, new)

    if any(r.method == MethodEnum.NODE_EXPORTER for r in (old, new) if r):
        send_node_exporter(rule, port, old, new)

    if any(r.method == MethodEnum.TINY_PORT_MAPPER for r in (old, new) if r):
        send_tiny_port_mapper(rule, port, old, new)

    if any(r.method == MethodEnum.SHADOWSOCKS for r in (old, new) if r):
        send_shadowsocks(rule, port, old, new)


def trigger_tc(port: Port):
    kwargs = {
        "server_id": port.server.id,
        "port_num": port.num,
        "egress_limit": port.config.get("egress_limit"),
        "ingress_limit": port.config.get("ingress_limit"),
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.tc.tc_runner", kwargs=kwargs)


def remove_tc(server_id: int, port_num: int):
    kwargs = {
        "server_id": server_id,
        "port_num": port_num,
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.tc.tc_runner", kwargs=kwargs)


def trigger_ansible_hosts():
    print(f"Sending ansible_hosts_runner task")
    celery_app.send_task("tasks.ansible.ansible_hosts_runner")


def trigger_iptables_reset(port: Port):
    kwargs = {"server_id": port.server.id, "port_num": port.num}
    print(f"Sending iptables.iptables_reset_runner task")
    celery_app.send_task("tasks.iptables.iptables_reset_runner", kwargs=kwargs)


def trigger_server_connect(server_id: int, init: bool = False, **kwargs):
    kwargs["server_id"] = server_id
    kwargs["sync_scripts"] = init
    kwargs["init_iptables"] = init
    print(f"Sending server.server_runner task")
    celery_app.send_task("tasks.server.server_runner", kwargs=kwargs)


def trigger_server_clean(server: Server):
    print(f"Sending clean.clean_runner task")
    celery_app.send_task(
        "tasks.clean.clean_runner",
        kwargs={"server": ServerEdit(**server.__dict__).dict()},
    )