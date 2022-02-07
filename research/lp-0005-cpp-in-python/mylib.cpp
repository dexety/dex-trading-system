/*
 * Tutorial: https://www.boost.org/doc/libs/1_75_0/libs/python/doc/html/tutorial/index.html
 */

#include <string>

class Person {
private:
    std::string name_;

public:
    Person() = default;

    Person(std::string name) : name_(name) {
    }

    void set_name(std::string new_name) {
        name_ = new_name;
    }

    std::string get_name() const {
        return name_;
    }
};

std::string hello() {
    return "Hi, Leo Proko!";
}

#include <boost/python.hpp>

BOOST_PYTHON_MODULE(mylib) {
    using namespace boost::python;
    def("hello", hello);
    class_<Person>("Person")
        .def(init<std::string>())
        .def("set_name", &Person::set_name)
        .def("get_name", &Person::get_name);
}
