#!/usr/bin/env python3

import math

import geometry_msgs.msg
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy, JointState
from std_msgs.msg import Float64MultiArray


CLAW_JOINT = "left_claw_joint"
CLAW_MIN = 0.0
CLAW_MAX = 0.249


class JoyClawTeleop(Node):
    def __init__(self):
        super().__init__("rangka_krai_joy_teleop")
        self.axis_forward = self.declare_parameter("axis_forward", 1).value
        self.axis_strafe = self.declare_parameter("axis_strafe", 0).value
        self.axis_turn = self.declare_parameter("axis_turn", 3).value
        self.axis_claw = self.declare_parameter("axis_claw", 4).value
        self.button_deadman = self.declare_parameter("button_deadman", 9).value
        self.button_deadman_alternate = self.declare_parameter(
            "button_deadman_alternate", 4
        ).value
        self.button_claw_close = self.declare_parameter("button_claw_close", 0).value
        self.button_claw_open = self.declare_parameter("button_claw_open", 1).value
        self.deadzone = self.declare_parameter("deadzone", 0.12).value
        self.linear_speed = self.declare_parameter("linear_speed", 0.5).value
        self.strafe_speed = self.declare_parameter("strafe_speed", 0.5).value
        self.angular_speed = self.declare_parameter("angular_speed", 0.8).value
        self.claw_speed = self.declare_parameter("claw_speed", 0.12).value
        self.joy_timeout = self.declare_parameter("joy_timeout", 0.25).value
        self._validate_parameters()

        self.drive_publisher = self.create_publisher(
            geometry_msgs.msg.TwistStamped, "/cmd_vel", 10
        )
        self.claw_publisher = self.create_publisher(
            Float64MultiArray, "/left_claw_controller/commands", 10
        )
        self.create_subscription(Joy, "/joy", self._joy_callback, 10)
        self.create_subscription(
            JointState, "/joint_states", self._joint_state_callback, 10
        )
        self.create_timer(0.05, self._watchdog_callback)

        self.claw_target = None
        self._last_joy_time = None
        self._last_joy_callback_time = None
        self._warned_missing_joint_state = False
        self.get_logger().info(
            f"Joystick teleop ready: hold button {self.button_deadman} (dead-man) "
            f"or {self.button_deadman_alternate} to drive; claw axis is {self.axis_claw}, "
            f"close/open buttons are {self.button_claw_close}/{self.button_claw_open}."
        )

    def _validate_parameters(self):
        indexes = (
            self.axis_forward,
            self.axis_strafe,
            self.axis_turn,
            self.axis_claw,
            self.button_deadman,
            self.button_deadman_alternate,
            self.button_claw_close,
            self.button_claw_open,
        )
        if any(not isinstance(index, int) or index < 0 for index in indexes):
            raise ValueError(
                "Joystick axis and button indexes must be non-negative integers."
            )
        if self.button_claw_close == self.button_claw_open:
            raise ValueError("Claw open and close buttons must be different.")
        if not math.isfinite(self.deadzone) or not 0.0 <= self.deadzone < 1.0:
            raise ValueError("deadzone must be in the range [0.0, 1.0).")
        for name, value in (
            ("linear_speed", self.linear_speed),
            ("strafe_speed", self.strafe_speed),
            ("angular_speed", self.angular_speed),
            ("claw_speed", self.claw_speed),
            ("joy_timeout", self.joy_timeout),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be a positive finite number.")

    @staticmethod
    def _read_index(values, index):
        if index >= len(values):
            return 0
        return values[index]

    def _axis(self, axes, index):
        value = self._read_index(axes, index)
        if not math.isfinite(value):
            return 0.0
        value = max(-1.0, min(1.0, value))
        if abs(value) <= self.deadzone:
            return 0.0
        return math.copysign(
            (abs(value) - self.deadzone) / (1.0 - self.deadzone), value
        )

    def _joint_state_callback(self, message):
        if self.claw_target is not None or CLAW_JOINT not in message.name:
            return
        index = message.name.index(CLAW_JOINT)
        if index < len(message.position) and math.isfinite(message.position[index]):
            self.claw_target = max(CLAW_MIN, min(CLAW_MAX, message.position[index]))

    def _joy_callback(self, message):
        now = self.get_clock().now()
        now_ns = now.nanoseconds
        elapsed = 0.05
        if self._last_joy_callback_time is not None:
            elapsed = max(
                0.0,
                min(0.1, (now_ns - self._last_joy_callback_time) / 1e9),
            )
        self._last_joy_callback_time = now_ns
        self._last_joy_time = now_ns

        buttons = message.buttons
        deadman = bool(
            self._read_index(buttons, self.button_deadman)
            or self._read_index(buttons, self.button_deadman_alternate)
        )
        twist = geometry_msgs.msg.TwistStamped()
        twist.header.stamp = now.to_msg()
        twist.header.frame_id = "base_footprint"
        if deadman:
            twist.twist.linear.x = (
                -self._axis(message.axes, self.axis_forward) * self.linear_speed
            )
            twist.twist.linear.y = (
                -self._axis(message.axes, self.axis_strafe) * self.strafe_speed
            )
            twist.twist.angular.z = (
                -self._axis(message.axes, self.axis_turn) * self.angular_speed
            )
        self.drive_publisher.publish(twist)

        if not deadman:
            return
        close_pressed = bool(self._read_index(buttons, self.button_claw_close))
        open_pressed = bool(self._read_index(buttons, self.button_claw_open))
        claw_axis = -self._axis(message.axes, self.axis_claw)
        if close_pressed and not open_pressed:
            claw_axis = -1.0
        elif open_pressed and not close_pressed:
            claw_axis = 1.0
        elif close_pressed and open_pressed:
            claw_axis = 0.0
        if claw_axis == 0.0:
            return
        if self.claw_target is None:
            if not self._warned_missing_joint_state:
                self.get_logger().warning(
                    "Cannot move the claw until left_claw_joint feedback arrives on /joint_states."
                )
                self._warned_missing_joint_state = True
            return
        self.claw_target = max(
            CLAW_MIN,
            min(
                CLAW_MAX,
                self.claw_target + claw_axis * self.claw_speed * elapsed,
            ),
        )
        self.claw_publisher.publish(
            Float64MultiArray(data=[float(self.claw_target)])
        )

    def _watchdog_callback(self):
        now = self.get_clock().now()
        if (
            self._last_joy_time is not None
            and (now.nanoseconds - self._last_joy_time) / 1e9 <= self.joy_timeout
        ):
            return
        stop = geometry_msgs.msg.TwistStamped()
        stop.header.stamp = now.to_msg()
        stop.header.frame_id = "base_footprint"
        self.drive_publisher.publish(stop)


def main(args=None):
    rclpy.init(args=args)
    node = JoyClawTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop = geometry_msgs.msg.TwistStamped()
        stop.header.stamp = node.get_clock().now().to_msg()
        stop.header.frame_id = "base_footprint"
        node.drive_publisher.publish(stop)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
