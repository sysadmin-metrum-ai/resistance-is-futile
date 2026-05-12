from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event


VARIANCE_WINDOW = 10
VARIANCE_THRESHOLD = 0.001
POST_CONVERGE_SETTLE_S = 0.5


@dataclass
class PreparedDrone:
    uri: str
    scf: object
    cf: object
    commander: object
    pose: tuple[float, float, float]
    timings: dict[str, float]


def cache_dir_for_uri(uri: str) -> str:
    suffix = uri.rstrip("/").split("/")[-1] or "default"
    return f"./cache/preflight-launch-{suffix}"


def parse_uri_list(raw: list[str]) -> list[str]:
    uris: list[str] = []
    for item in raw:
        uris.extend(part.strip() for part in item.split(",") if part.strip())
    return list(dict.fromkeys(uris))


def wait_for_estimator(cf, log_cls, timeout_s: float) -> None:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    log = log_cls(name=f"ProbeVar{int(time.time() * 1000) % 100000}", period_in_ms=100)
    log.add_variable("kalman.varPX", "float")
    log.add_variable("kalman.varPY", "float")
    log.add_variable("kalman.varPZ", "float")

    def on_data(_ts, data, _conf) -> None:
        xs.append(float(data["kalman.varPX"]))
        ys.append(float(data["kalman.varPY"]))
        zs.append(float(data["kalman.varPZ"]))

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if _variance_ready(xs, ys, zs):
                time.sleep(POST_CONVERGE_SETTLE_S)
                return
            time.sleep(0.1)
        raise RuntimeError(f"kalman variance did not converge in {timeout_s}s")
    finally:
        log.stop()
        _delete_log(log)


def read_pose(cf, log_cls, sample_s: float) -> tuple[float, float, float]:
    sample: dict = {}
    ready = Event()
    log = log_cls(name=f"ProbePose{int(time.time() * 1000) % 100000}", period_in_ms=100)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")

    def on_data(_ts, data, _conf) -> None:
        sample.update(data)
        ready.set()

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        ready.wait(sample_s)
        if not sample:
            raise RuntimeError("no pose sample received")
        return (
            float(sample["kalman.stateX"]),
            float(sample["kalman.stateY"]),
            float(sample["kalman.stateZ"]),
        )
    finally:
        log.stop()
        _delete_log(log)


def prepare_drone(uri: str, args) -> PreparedDrone:
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.log import LogConfig
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

    timings: dict[str, float] = {}
    started = time.monotonic()
    scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
    scf.open_link()
    cf = scf.cf
    timings["connect_s"] = time.monotonic() - started

    configure_started = time.monotonic()
    cf.param.set_value("stabilizer.estimator", "2")
    cf.param.set_value("commander.enHighLevel", "1")
    if args.collision_avoidance:
        cf.param.set_value("stabilizer.controller", "1")
        cf.param.set_value("colAv.enable", "1")
    time.sleep(args.param_settle_s)
    timings["param_s"] = time.monotonic() - configure_started

    estimator_started = time.monotonic()
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")
    wait_for_estimator(cf, LogConfig, args.estimator_timeout_s)
    timings["estimator_s"] = time.monotonic() - estimator_started

    pose_started = time.monotonic()
    pose = read_pose(cf, LogConfig, args.pose_sample_s)
    timings["pose_s"] = time.monotonic() - pose_started

    arm_started = time.monotonic()
    if hasattr(cf, "supervisor"):
        cf.supervisor.send_arming_request(True)
    else:
        cf.platform.send_arming_request(True)
    time.sleep(args.arm_settle_s)
    timings["arm_s"] = time.monotonic() - arm_started
    timings["total_s"] = time.monotonic() - started
    return PreparedDrone(uri, scf, cf, cf.high_level_commander, pose, timings)


def _variance_ready(xs: list[float], ys: list[float], zs: list[float]) -> bool:
    if len(xs) < VARIANCE_WINDOW or len(ys) < VARIANCE_WINDOW or len(zs) < VARIANCE_WINDOW:
        return False
    return (
        max(xs[-VARIANCE_WINDOW:]) - min(xs[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
        and max(ys[-VARIANCE_WINDOW:]) - min(ys[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
        and max(zs[-VARIANCE_WINDOW:]) - min(zs[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
    )


def _delete_log(log) -> None:
    try:
        log.delete()
    except Exception:
        pass
