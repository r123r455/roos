cmake_minimum_required(VERSION 3.8)
project(rangka_krai_2027)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch meshes urdf worlds
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/teleop_twist_keyboard_claw.py
    scripts/teleop_joy_claw.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
