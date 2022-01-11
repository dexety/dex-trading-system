class Stack:
    def __init__(self, func) -> None:
        self.stack = []
        self.prefs = []
        self.func = func

    def push(self, elem):
        if len(self.stack) == 0:
            self.prefs.append(elem)
        else:
            self.prefs.append(self.func(self.prefs[-1], elem))

        self.stack.append(elem)

    def pop(self):
        temp = self.stack[-1]
        self.stack.pop()
        self.prefs.pop()

        return temp


class Queue:
    def __init__(self, func) -> None:
        self.head = Stack(func)
        self.tail = Stack(func)
        self.func = func

    def push(self, elem):
        self.head.push(elem)

    def pop(self):
        if len(self.tail.stack) == 0:
            while len(self.head.stack) > 0:
                self.tail.push(self.head.pop())
        return self.tail.pop()

    def best(self):
        if len(self.tail.stack) == 0:
            return self.head.prefs[-1]
        if len(self.head.stack) == 0:
            return self.tail.prefs[-1]
        return self.func(self.head.prefs[-1], self.tail.prefs[-1])

    def back(self):
        if len(self.tail.stack) != 0:
            return self.tail.stack[-1]
        return self.head.stack[0]

    def size(self):
        return len(self.tail.stack) + len(self.head.stack)
