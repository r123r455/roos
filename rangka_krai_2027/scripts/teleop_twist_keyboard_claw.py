#!/usr/bin/env python3

import threading
import time

import geometry_msgs.msg
import rclpy
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from teleop_twist_keyboard import (
    getKey,
    moveBindings,
    restoreTerminalSettings,
    saveTerminalSettings,
    speedBindings,
    vels,
)


CLAW_JOINT = "left_claw_joint"
CLAW_MIN = 0.0
CLAW_MAX = 0.249
CLAW_STEP = 0.01
CLAW_BINDINGS = {
    "a": -CLAW_STEP,
    "A": -CLAW_STEP,
    "d": CLAW_STEP,
    "D": CLAW_STEP,
    "g": CLAW_MIN,
    "G": CLAW_MIN,
    "h": CLAW_MAX,
    "H": CLAW_MAX,
}

HELP = """
Robot movement (same as teleop_twist_keyboard):
   u    i    o
   j    k    l
   m    ,    .
Uppercase keys strafe; q/z, w/x, e/c adjust speed.

Left claw:
   a/A : close a little          d/D : open a little
   g/G : close fully              h/H : open fully
   The full left claw carriage slides toward the robot's left.
   Left claw slides horizontally; positions are in metres.
   Current joint position is shown after each claw command.
Click this terminal first so it receives the keyboard keys.
Ctrl-C to quit.
"""


def clamp_claw_position(position):
    return max(CLAW_MIN, min(CLAW_MAX, position))


def main():
    settings = saveTerminalSettings()
    rclpy.init()
    node = rclpy.create_node("rangka_krai_keyboard_teleop")
    twist_publisher = node.create_publisher(
        geometry_msgs.msg.TwistStamped, "/cmd_vel", 10
    )
    claw_publisher = node.create_publisher(
        Float64MultiArray, "/left_claw_controller/commands", 10
    )
    state = {"position": None}

    def update_joint_state(message):
        if CLAW_JOINT in message.name:
            index = message.name.index(CLAW_JOINT)
            if index < len(message.position):
                state["position"] = message.position[index]

    node.create_subscription(JointState, "/joint_states", update_joint_state, 10)
    spinner = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spinner.start()

    connection_deadline = time.monotonic() + 5.0
    while (
        time.monotonic() < connection_deadline
        and (
            twist_publisher.get_subscription_count() == 0
            or claw_publisher.get_subscription_count() == 0
        )
    ):
        time.sleep(0.05)

    speed = 0.8
    turn = 1.2
    x = y = z = th = 0.0
    claw_target = CLAW_MIN
    claw_target_initialized = False
    status = 0

    try:
        print(HELP)
        print(vels(speed, turn))
        print(
            "Drive controller connected on /cmd_vel."
            if twist_publisher.get_subscription_count()
            else "WARNING: no drive controller is subscribed to /cmd_vel."
        )
        print(
            "Claw controller connected on /left_claw_controller/commands."
            if claw_publisher.get_subscription_count()
            else "WARNING: no claw controller is subscribed to /left_claw_controller/commands."
        )
        while True:
            key = getKey(settings)
            if key in CLAW_BINDINGS:
                if key.lower() in ("g", "h"):
                    claw_target = CLAW_BINDINGS[key]
                    claw_target_initialized = True
                else:
                    if not claw_target_initialized:
                        if state["position"] is not None:
                            claw_target = clamp_claw_position(state["position"])
                        claw_target_initialized = True
                    claw_target = clamp_claw_position(
                        claw_target + CLAW_BINDINGS[key]
                    )
                claw_publisher.publish(
                    Float64MultiArray(data=[float(claw_target)])
                )
                if not claw_publisher.get_subscription_count():
                    print(
                        "ERROR: no claw controller is subscribed. "
                        "Check that left_claw_controller is active."
                    )
                else:
                    measured = state["position"]
                    measured_text = (
                        f"{measured:.3f} m"
                        if measured is not None
                        else "waiting for joint state"
                    )
                    print(
                        f"Left claw target: {claw_target:.3f} m "
                        f"(measured: {measured_text})"
                    )
                x = y = z = th = 0.0
            elif key in moveBindings:
                x, y, z, th = moveBindings[key]
            elif key in speedBindings:
                speed *= speedBindings[key][0]
                turn *= speedBindings[key][1]
                print(vels(speed, turn))
                if status == 14:
                    print(HELP)
                status = (status + 1) % 15
            else:
                x = y = z = th = 0.0
                if key == "\x03":
                    break

            message = geometry_msgs.msg.TwistStamped()
            message.header.stamp = node.get_clock().now().to_msg()
            message.header.frame_id = "base_footprint"
            message.twist.linear.x = x * speed
            message.twist.linear.y = y * speed
            message.twist.linear.z = z * speed
            message.twist.angular.z = th * turn
            twist_publisher.publish(message)
    finally:
        stop = geometry_msgs.msg.TwistStamped()
        stop.header.stamp = node.get_clock().now().to_msg()
        stop.header.frame_id = "base_footprint"
        twist_publisher.publish(stop)
        rclpy.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        restoreTerminalSettings(settings)


if __name__ == "__main__":
    main()
