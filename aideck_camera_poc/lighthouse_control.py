from __future__ import annotations

import time

from camera_socket import status


ESTIMATOR_WINDOW = 10
ESTIMATOR_VARIANCE_RANGE_MAX = 0.001


def cache_dir_for_uri(uri: str) -> str:
    suffix = uri.rstrip("/").split("/")[-1]
    return f"./cache/{suffix}"


def reset_estimator(cf) -> None:
    status("[drone] Resetting Kalman estimator...")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")


def wait_for_estimator(cf, timeout_s: float) -> None:
    from cflib.crazyflie.log import LogConfig

    status("[drone] Waiting for Lighthouse/Kalman convergence...")
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    logconf = LogConfig(name="EstimatorVarCameraPoc", period_in_ms=100)
    logconf.add_variable("kalman.varPX", "float")
    logconf.add_variable("kalman.varPY", "float")
    logconf.add_variable("kalman.varPZ", "float")

    def on_data(_timestamp, data, _logconf) -> None:
        xs.append(float(data["kalman.varPX"]))
        ys.append(float(data["kalman.varPY"]))
        zs.append(float(data["kalman.varPZ"]))

    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    deadline = time.time() + timeout_s

    try:
        while time.time() < deadline:
            if len(xs) >= ESTIMATOR_WINDOW:
                range_x = max(xs[-ESTIMATOR_WINDOW:]) - min(xs[-ESTIMATOR_WINDOW:])
                range_y = max(ys[-ESTIMATOR_WINDOW:]) - min(ys[-ESTIMATOR_WINDOW:])
                range_z = max(zs[-ESTIMATOR_WINDOW:]) - min(zs[-ESTIMATOR_WINDOW:])
                if (
                    range_x < ESTIMATOR_VARIANCE_RANGE_MAX
                    and range_y < ESTIMATOR_VARIANCE_RANGE_MAX
                    and range_z < ESTIMATOR_VARIANCE_RANGE_MAX
                ):
                    status("[drone] Estimator converged.")
                    return
            time.sleep(0.1)
    finally:
        logconf.stop()

    raise RuntimeError("Kalman estimator did not converge")


def arm_if_supported(cf) -> None:
    status("[drone] Sending arming request...")
    if hasattr(cf, "supervisor"):
        cf.supervisor.send_arming_request(True)
    else:
        cf.platform.send_arming_request(True)
    time.sleep(1.0)


def configure_drone(cf, estimator_timeout: float) -> None:
    status("[drone] Enabling Kalman estimator and high-level commander...")
    cf.param.set_value("stabilizer.estimator", "2")
    cf.param.set_value("commander.enHighLevel", "1")
    time.sleep(0.5)
    reset_estimator(cf)
    wait_for_estimator(cf, estimator_timeout)
    arm_if_supported(cf)
