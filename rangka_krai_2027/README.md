# Rangka Krai 2027 — ROS 2 + Gazebo

This package contains a ROS 2 Jazzy description and a Gazebo Sim Harmonic
bringup for the mecanum-drive robot. The original Onshape URDF and ROS 1 launch
file are retained; `urdf/rangka_krai_2027.urdf.xacro` is the simulation model.

## Model and assumptions

- The CAD mesh assembly is split into a chassis and four driven wheel links.
  The eight roller meshes in each Mecanum assembly are passive rotating links,
  so the wheel collision geometry can roll laterally as well as forward.
- The wheel centers and ground plane are estimated from the STL assembly.
  Chassis collision uses simplified boxes; roller collisions use cylinders
  fitted to the roller meshes.
- Masses (5 kg chassis, 0.20 kg per wheel, 0.012 kg per roller) and inertias
  are simulation estimates, not measured specifications. Adjust the Xacro
  arguments and controller geometry after weighing/measuring the physical
  robot.

## Install and build

Install the ROS dependencies with `rosdep`, then build this package in a ROS 2
Jazzy workspace:

```bash
sudo apt update
sudo apt install ros-jazzy-ros2-control ros-jazzy-mecanum-drive-controller \
  ros-jazzy-joint-state-broadcaster ros-jazzy-position-controllers \
  ros-jazzy-gz-ros2-control
rosdep update
rosdep install --from-paths src/rangka_krai_2027 --ignore-src -r -y
colcon build --packages-select rangka_krai_2027
source install/setup.bash
```

The package requires `gz_ros2_control`, `mecanum_drive_controller`,
`joint_state_broadcaster`, `position_controllers`, `ros_gz_sim`,
`ros_gz_bridge`, and `teleop_twist_keyboard`.

If the original CAD assembly changes, regenerate the Xacro mesh partitioning
with:

```bash
python3 src/rangka_krai_2027/scripts/generate_robot_xacro.py
```

After changing the assembly, also remeasure the wheel radius and wheel-center
spacing in `config/ros2_controllers.yaml`.

## Run and control

From the package folder, start the build, Gazebo, KRI field, robot spawn, and
controllers with one command:

```bash
./run_simulation.sh
```

The script uses `../Lapangan_KRI_2027/lapangan.world` when present and spawns
the robot at the red starting zone facing the center. Otherwise, it falls back
to the package's empty Gazebo world. If control dependencies are missing, it
offers to install them with `sudo`.

Pass launch options after the script name to change the world or spawn pose:

```bash
./run_simulation.sh spawn_x:=-4.4 spawn_y:=-5.15 spawn_yaw:=1.5708
```

The world path can also be set with `world:=/path/to/world.sdf`, and the spawn
pose can be adjusted with `spawn_x`, `spawn_y`, `spawn_z`, and `spawn_yaw`
(radians).

Optionally open keyboard teleoperation in a separate terminal window:

```bash
./run_simulation.sh use_teleop:=true
```

The keyboard controls appear in the new terminal window. Keep that window
focused while driving or operating the claw; close it or press `Ctrl+C` there
to stop teleoperation.

### USB joystick (including wired PS3 controllers)

Install the ROS 2 joystick driver and Linux joystick utilities if needed:

```bash
sudo apt install ros-jazzy-joy joystick
```

Connect the controller, then start the simulation and joystick teleop together:

```bash
./run_simulation.sh use_joy_teleop:=true
```

The joystick driver publishes `/joy`; the teleop node publishes drive commands
to `/cmd_vel` and claw positions to `/left_claw_controller/commands`. Hold
**L1** (gas/dead-man) while using the sticks or claw buttons. **Select** also
works as an alternate gas/dead-man button. Releasing both, losing joystick
messages, or stopping the teleop node sends a zero drive command.
The left stick drives and strafes, the right stick turns, and moving the right
stick up/down opens/closes the claw. **X** closes and **Circle** opens the claw
as alternate controls. Holding the stick or a claw button moves the carriage
gradually; release it at any point to hold its current position. Only run one
teleop mode at a time (keyboard or joystick).

The default PS3/Linux mapping is in
[`config/joy_teleop.yaml`](config/joy_teleop.yaml): left-stick axes `1/0`,
right-stick horizontal/vertical axes `3/4`, L1 dead-man button `9`, X button
`0`, Circle button `1`, and Select alternate gas button `4`. This uses the
standard SDL game-controller button order from `joy_node`. Other drivers may
report different indices. Check the actual mapping with `ros2 topic echo /joy`
and edit this YAML if needed. If Linux does not expose the controller, check
`lsusb` and `/dev/input/js0`, and verify access permissions for the current user.

The same keyboard terminal controls both the mecanum drive and left claw:

| Key | Action |
| --- | --- |
| `u i o`, `j k l`, `m , .` | Drive and turn |
| Uppercase movement keys | Strafe |
| `q/z`, `w/x`, `e/c` | Adjust drive speeds |
| `a/A` / `d/D` | Close / open the full left carriage by 0.01 m |
| `g/G` / `h/H` | Close / open fully |

Default keyboard speed is `0.8 m/s` and turn speed is `1.2 rad/s`.
Joystick full deflection requests up to `1.0 m/s` in either linear direction
and `1.2 rad/s` rotation. The mecanum controller limits linear speed to
`1.0 m/s` and rotation to `1.5 rad/s`. These are simulation settings; test
gradually and reduce them if the robot slips, tips, or moves too aggressively.

Claw commands are clamped to `0.0` through approximately `0.249` m. The
front-left semicircular jaw, its mounting pieces, and the MGN12 carriage slide
together toward the robot's left; the guide rail and right-side jaw stay fixed.
The usable maximum is calculated from the CAD rail/carriage bounds with a 1 cm
end margin. The terminal prints the requested slide distance and measured
joint position when feedback is available.

The mecanum controller accepts `geometry_msgs/msg/TwistStamped` on
`/cmd_vel`. For example:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/TwistStamped \
  "{header: {frame_id: base_footprint}, twist: {linear: {x: 0.1}}}"
```

Joint feedback is published on `/joint_states`; wheel odometry and its TF are
published on `/odom` and `odom -> base_footprint`. The controller stops when
its reference has not been refreshed for 0.5 seconds.

The full front-left claw carriage is exposed as the single prismatic joint
`left_claw_joint`; the mirrored right claw and MGN12 guide rail remain fixed.
Its simulation position range is `0.0` to approximately `0.249` m, derived
from the CAD rail length and carriage position. In this CAD pose, `0.0` is
closed and positive values slide the complete left assembly toward the robot's
left. It can also be controlled directly from another terminal:

```bash
# Open to the CAD-derived travel limit
ros2 topic pub --once /left_claw_controller/commands \
  std_msgs/msg/Float64MultiArray "{data: [0.249]}"

# Close
ros2 topic pub --once /left_claw_controller/commands \
  std_msgs/msg/Float64MultiArray "{data: [0.0]}"
```

The original CAD URDF has no joint or actuator data for the claw. The movable
CAD assembly includes 43 front MGN12 carriage meshes plus the semicircular jaw,
shaft, and left mounting pieces; the long MGN12 rail remains on the chassis.
The ROS 2 prismatic joint acts as the simulated linear drive because the CAD
does not identify a separate linear actuator. Gazebo uses fitted collision
boxes on both opposing jaw faces, derived from their CAD meshes; the moving
collision is limited to the left jaw instead of one oversized box around the
entire carriage. This lets Sky Blocks and Earth Boxes make physical contact
with both jaws. The collision boxes include 2 mm padding. The jaw `mu1`/`mu2`
tags do not appear in the generated Gazebo SDF, so Gazebo's default contact
friction is used; successful gripping and lifting still need runtime
validation. The 1 cm rail-end margin and 0.25 kg assembly mass are also
simulation assumptions. Confirm the real actuator, mechanical end stops, and
safe travel before using these values with hardware.
