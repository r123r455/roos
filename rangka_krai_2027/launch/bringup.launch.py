from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    RegisterEventHandler,
    SetEnvironmentVariable,
    Shutdown,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    EnvironmentVariable,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackagePrefix, FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare("rangka_krai_2027")
    world = LaunchConfiguration("world")
    use_teleop = LaunchConfiguration("use_teleop")
    use_joy_teleop = LaunchConfiguration("use_joy_teleop")
    joy_config = PathJoinSubstitution(
        [package_share, "config", "joy_teleop.yaml"]
    )
    model_path = PathJoinSubstitution(
        [package_share, "urdf", "rangka_krai_2027.urdf.xacro"]
    )
    robot_description = Command(
        [
            FindExecutable(name="xacro"),
            " ",
            model_path,
            " chassis_mass:=",
            LaunchConfiguration("chassis_mass"),
        ]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"]
            )
        ),
        launch_arguments={"gz_args": ["-r -v 3 ", world]}.items(),
    )
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[
            {
                "robot_description": robot_description,
                "use_sim_time": True,
            }
        ],
        output="screen",
    )
    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-topic",
            "robot_description",
            "-name",
            "rangka_krai_2027",
            "-z",
            LaunchConfiguration("spawn_z"),
            "-x",
            LaunchConfiguration("spawn_x"),
            "-y",
            LaunchConfiguration("spawn_y"),
            "-Y",
            LaunchConfiguration("spawn_yaw"),
        ],
        output="screen",
    )
    spawn_joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            "/controller_manager",
        ],
        output="screen",
    )
    spawn_mecanum_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "mecanum_drive_controller",
            "--controller-manager",
            "/controller_manager",
        ],
        output="screen",
    )
    spawn_left_claw_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "left_claw_controller",
            "--controller-manager",
            "/controller_manager",
        ],
        output="screen",
    )
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        parameters=[{"use_sim_time": True}],
        output="screen",
    )
    teleop = Node(
        package="rangka_krai_2027",
        executable="teleop_twist_keyboard_claw.py",
        prefix="x-terminal-emulator -e",
        output="screen",
        condition=IfCondition(use_teleop),
    )
    joy_driver = Node(
        package="joy",
        executable="joy_node",
        name="joy_node",
        parameters=[joy_config],
        output="screen",
        condition=IfCondition(use_joy_teleop),
    )
    joy_teleop = Node(
        package="rangka_krai_2027",
        executable="teleop_joy_claw.py",
        name="rangka_krai_joy_teleop",
        parameters=[joy_config],
        output="screen",
        condition=IfCondition(use_joy_teleop),
    )

    def start_joint_state_broadcaster(event, _context):
        if event.returncode != 0:
            message = (
                "Robot spawn failed "
                f"(exit code {event.returncode}); controllers will not be started."
            )
            return [LogInfo(msg=f"ERROR: {message}"), Shutdown(reason=message)]
        return [spawn_joint_state_broadcaster]

    def start_mecanum_controller(event, _context):
        if event.returncode != 0:
            message = (
                "Joint state broadcaster failed "
                f"(exit code {event.returncode}); mecanum controller will not start."
            )
            return [LogInfo(msg=f"ERROR: {message}"), Shutdown(reason=message)]
        return [spawn_mecanum_controller]

    def start_left_claw_controller(event, _context):
        if event.returncode != 0:
            message = (
                "Mecanum controller failed "
                f"(exit code {event.returncode}); the left claw controller will not start."
            )
            return [LogInfo(msg=f"ERROR: {message}"), Shutdown(reason=message)]
        return [spawn_left_claw_controller]

    def verify_left_claw_controller(event, _context):
        if event.returncode != 0:
            message = (
                "Left claw controller failed "
                f"(exit code {event.returncode})."
            )
            return [LogInfo(msg=f"ERROR: {message}"), Shutdown(reason=message)]
        return [
            LogInfo(
                msg=(
                    "Drive and claw controllers are ready; "
                    "starting keyboard teleoperation."
                )
            ),
            teleop,
        ]

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value=PathJoinSubstitution(
                    [package_share, "worlds", "empty.sdf"]
                ),
                description="Gazebo Sim world to start.",
            ),
            DeclareLaunchArgument(
                "use_teleop",
                default_value="false",
                description="Start keyboard teleoperation in this terminal.",
            ),
            DeclareLaunchArgument(
                "use_joy_teleop",
                default_value="false",
                description="Start joystick teleoperation using the connected USB controller.",
            ),
            DeclareLaunchArgument(
                "chassis_mass",
                default_value="5.0",
                description="Estimated chassis mass in kg; calibrate against the real robot.",
            ),
            DeclareLaunchArgument(
                "spawn_x",
                default_value="0.0",
                description="Initial robot x position in the selected world.",
            ),
            DeclareLaunchArgument(
                "spawn_y",
                default_value="0.0",
                description="Initial robot y position in the selected world.",
            ),
            DeclareLaunchArgument(
                "spawn_z",
                default_value="0.01",
                description="Initial robot z position in the selected world.",
            ),
            DeclareLaunchArgument(
                "spawn_yaw",
                default_value="0.0",
                description="Initial robot yaw in radians.",
            ),
            SetEnvironmentVariable(
                "GZ_SIM_RESOURCE_PATH",
                [
                    PathJoinSubstitution(
                        [FindPackagePrefix("rangka_krai_2027"), "share"]
                    ),
                    ":",
                    EnvironmentVariable("GZ_SIM_RESOURCE_PATH", default_value=""),
                ],
            ),
            gazebo,
            robot_state_publisher,
            clock_bridge,
            spawn_robot,
            RegisterEventHandler(
                OnProcessExit(
                    target_action=spawn_robot,
                    on_exit=start_joint_state_broadcaster,
                )
            ),
            RegisterEventHandler(
                OnProcessExit(
                    target_action=spawn_joint_state_broadcaster,
                    on_exit=start_mecanum_controller,
                )
            ),
            RegisterEventHandler(
                OnProcessExit(
                    target_action=spawn_mecanum_controller,
                    on_exit=start_left_claw_controller,
                )
            ),
            RegisterEventHandler(
                OnProcessExit(
                    target_action=spawn_left_claw_controller,
                    on_exit=verify_left_claw_controller,
                )
            ),
            joy_driver,
            joy_teleop,
        ]
    )
