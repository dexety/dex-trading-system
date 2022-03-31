class Stack:
    def __init__(self) -> None:
        self.stack = []
        self.max_prefs = []
        self.min_prefs = []

    def push(self, elem):
        if len(self.stack) == 0:
            self.max_prefs.append(elem)
            self.min_prefs.append(elem)
        else:
            self.max_prefs.append(max(self.max_prefs[-1], elem))
            self.min_prefs.append(min(self.min_prefs[-1], elem))

        self.stack.append(elem)

    def pop(self):
        temp = self.stack[-1]
        self.stack.pop()
        self.max_prefs.pop()
        self.min_prefs.pop()

        return temp
    
    def clear(self):
        self.stack.clear()
        self.max_prefs.clear()
        self.min_prefs.clear()


class Queue:
    def __init__(self) -> None:
        self.head = Stack()
        self.tail = Stack()

    def push(self, elem) -> bool:
        self.head.push(elem)

    def pop(self):
        if len(self.tail.stack) == 0:
            while len(self.head.stack) > 0:
                self.tail.push(self.head.pop())
        return self.tail.pop()

    def max(self):
        if len(self.tail.stack) == 0:
            return self.head.max_prefs[-1]
        if len(self.head.stack) == 0:
            return self.tail.max_prefs[-1]
        return max(self.head.max_prefs[-1], self.tail.max_prefs[-1])

    def min(self):
        if len(self.tail.stack) == 0:
            return self.head.min_prefs[-1]
        if len(self.head.stack) == 0:
            return self.tail.min_prefs[-1]
        return min(self.head.min_prefs[-1], self.tail.min_prefs[-1])

    def back(self):
        if len(self.tail.stack) != 0:
            return self.tail.stack[-1]
        return self.head.stack[0]

    def size(self):
        return len(self.tail.stack) + len(self.head.stack)
    
    def clear(self):
        self.head.clear()
        self.tail.clear()
