#!/usr/bin/env bash
set -Ee -o pipefail

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
PACKAGE_NAME="rangka_krai_2027"
FIELD_WORLD="${KRI_FIELD_WORLD:-${PACKAGE_DIR}/../Lapangan_KRI_2027/lapangan.world}"
DEFAULT_WORLD="${PACKAGE_DIR}/worlds/empty.sdf"

if [[ ! -r "${ROS_SETUP}" ]]; then
  printf 'ROS 2 Jazzy setup not found: %s\n' "${ROS_SETUP}" >&2
  exit 1
fi

source "${ROS_SETUP}"

if ! command -v colcon >/dev/null 2>&1; then
  printf 'colcon is required. Install it with: sudo apt install python3-colcon-common-extensions\n' >&2
  exit 1
fi

if [[ ! -x "$(command -v gz || true)" ]]; then
  printf 'Gazebo Sim (gz) is required. Install Gazebo Harmonic before continuing.\n' >&2
  exit 1
fi

if [[ -f "${FIELD_WORLD}" ]]; then
  DEFAULT_WORLD="${FIELD_WORLD}"
  DEFAULT_SPAWN_X="-5.15"
  DEFAULT_SPAWN_Y="-5.15"
  DEFAULT_SPAWN_YAW="1.5708"
  printf 'Using KRI field: %s\n' "${DEFAULT_WORLD}"
else
  DEFAULT_SPAWN_X="0.0"
  DEFAULT_SPAWN_Y="0.0"
  DEFAULT_SPAWN_YAW="0.0"
  printf 'KRI field not found at %s; using the package empty world.\n' "${FIELD_WORLD}"
fi

declare -a required_packages=(
  ament_index_python
  controller_manager
  joy
  mecanum_drive_controller
  joint_state_broadcaster
  position_controllers
  gz_ros2_control
  launch
  launch_ros
  robot_state_publisher
  ros_gz_bridge
  ros_gz_sim
  rosgraph_msgs
  teleop_twist_keyboard
  xacro
)
declare -a missing_packages=()
for package in "${required_packages[@]}"; do
  if ! ros2 pkg prefix "${package}" >/dev/null 2>&1; then
    missing_packages+=("${package}")
  fi
done

if (( ${#missing_packages[@]} > 0 )); then
  declare -a apt_packages=()
  for package in "${missing_packages[@]}"; do
    apt_packages+=("ros-jazzy-${package//_/-}")
  done
  printf 'Missing ROS 2 runtime dependencies: %s\n' "${missing_packages[*]}" >&2
  printf 'They are needed to load the Gazebo control plugin and start the robot controllers.\n' >&2
  if [[ ! -t 0 ]]; then
    printf 'Install them with: sudo apt install %s\n' "${apt_packages[*]}" >&2
    exit 1
  fi
  read -r -p "Install missing packages now? [y/N] " answer
  if [[ ! "${answer}" =~ ^[Yy]$ ]]; then
    printf 'Install them with: sudo apt install %s\n' "${apt_packages[*]}" >&2
    exit 1
  fi
  sudo apt install -y "${apt_packages[@]}"
  source "${ROS_SETUP}"
fi

CACHE_ROOT="${XDG_CACHE_HOME:-${HOME}/.cache}/rangka_krai_2027"
mkdir -p "${CACHE_ROOT}"

printf 'Building %s...\n' "${PACKAGE_NAME}"
colcon \
  --log-base "${CACHE_ROOT}/log" \
  build \
  --base-paths "${PACKAGE_DIR}" \
  --build-base "${CACHE_ROOT}/build" \
  --install-base "${CACHE_ROOT}/install"

source "${CACHE_ROOT}/install/setup.bash"

world="${DEFAULT_WORLD}"
spawn_x="${DEFAULT_SPAWN_X}"
spawn_y="${DEFAULT_SPAWN_Y}"
spawn_z="0.01"
spawn_yaw="${DEFAULT_SPAWN_YAW}"
declare -a extra_arguments=()

for argument in "$@"; do
  case "${argument}" in
    world:=*) world="${argument#world:=}" ;;
    spawn_x:=*) spawn_x="${argument#spawn_x:=}" ;;
    spawn_y:=*) spawn_y="${argument#spawn_y:=}" ;;
    spawn_z:=*) spawn_z="${argument#spawn_z:=}" ;;
    spawn_yaw:=*) spawn_yaw="${argument#spawn_yaw:=}" ;;
    *) extra_arguments+=("${argument}") ;;
  esac
done

for argument in "${extra_arguments[@]}"; do
  if [[ "${argument}" == "use_teleop:=true" ]] && ! command -v x-terminal-emulator >/dev/null 2>&1; then
    printf 'Keyboard teleop needs a graphical terminal. Install xterm with: sudo apt install xterm\n' >&2
    exit 1
  fi
done

printf 'Starting Gazebo and the robot controllers...\n'
exec ros2 launch "${PACKAGE_NAME}" bringup.launch.py \
  "world:=${world}" \
  "spawn_x:=${spawn_x}" \
  "spawn_y:=${spawn_y}" \
  "spawn_z:=${spawn_z}" \
  "spawn_yaw:=${spawn_yaw}" \
  "${extra_arguments[@]}"
