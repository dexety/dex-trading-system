from build import mylib

print(mylib.hello())

person = mylib.Person("Leo")
print(person.get_name())
person.set_name("Proko")
print(person.get_name())
