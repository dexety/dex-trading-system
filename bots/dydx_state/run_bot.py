import json
from threading import Thread
from handler import run_handler
from sender import run_sender


def init_users_data():
    with open("users.json", "w", encoding="utf-8") as file:
        json.dump({"users": {}}, file, indent=4)


def run_bot():
    init_users_data()

    handler_thread = Thread(target=run_handler)
    handler_thread.start()

    sender_thread = Thread(target=run_sender)
    sender_thread.start()


if __name__ == "__main__":
    run_bot()
