cmake_minimum_required(VERSION 3.5)

project("My lib")

# find python and Boost
find_package(PythonLibs 3.8 REQUIRED)
find_package(Boost COMPONENTS python REQUIRED)

# remove `lib` prefix
set(CMAKE_SHARED_MODULE_PREFIX "")

# add sources
add_library(mylib MODULE mylib.cpp)

# Set up the libraries and header
target_link_libraries(mylib ${Boost_LIBRARIES} ${PYTHON_LIBRARIES})
target_include_directories(mylib PRIVATE ${PYTHON_INCLUDE_DIRS})
