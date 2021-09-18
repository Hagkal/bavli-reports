import logging
import queue
import threading
from threading import Thread
from tkinter import ttk, DISABLED, NORMAL, NSEW
from tkinter.scrolledtext import ScrolledText
import tkinter as tk
from tkinter import N, W, S, E, Tk, BooleanVar

import validators

from bavli_reports.report_worker import do_report_work

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def thread_worker(**kwargs):
    logger.info("Starting the magic... \U0001F52E \U00002728 \U0001F609")

    def logging_func(msg, level=logging.INFO):
        logger.log(level, msg)

    def do_work():
        try:
            do_report_work(bavli_report_url=bavli_url.get(), external_report_url=external_url.get(),
                           logging_func=logging_func)
        except Exception as e:
            logger.error(f"Oops something went wrong! {e}")

    threading.Thread(target=do_work).start()


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue

    It can be used from different threads
    """

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


class ConsoleUi:
    """Poll messages from a logging queue and display them in a scrolled text widget"""

    def __init__(self, frame):
        self.frame = frame
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # Create a ScrolledText wdiget
        self.scrolled_text = ScrolledText(frame, state='disabled', background='white')
        self.scrolled_text.grid(row=0, column=0, rowspan=3, columnspan=3, sticky=NSEW)
        self.scrolled_text.configure(font=('TkFixedFont', 16))
        self.scrolled_text.tag_config('NOTSET', foreground='green')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('DEBUG', foreground='purple')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=1)
        # Create a logging handler using a queue
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter(fmt='%(asctime)s Hagai says: %(message)s', datefmt='%H:%M:%S')
        self.queue_handler.setFormatter(formatter)
        self.queue_handler.setLevel(logging.DEBUG)
        logger.addHandler(self.queue_handler)
        # Start polling messages from the queue
        self.frame.after(100, self.poll_log_queue)

    def display(self, record):
        msg = self.queue_handler.format(record)
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        # Autoscroll to the bottom
        self.scrolled_text.yview(tk.END)

    def poll_log_queue(self):
        # Check every 100ms if there is a new message in the queue to display
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display(record)
        self.frame.after(100, self.poll_log_queue)


if __name__ == "__main__":
    urls = []


    def check_both_url():
        for url in urls:
            if not validators.url(url.get()):
                start_button["state"] = DISABLED
                return
        start_button["state"] = NORMAL
        logger.info("Ok we are all set!")


    root = Tk()
    root.title("Report Master")
    s = ttk.Style()
    s.configure("Go.TButton", foreground='green', font=('Ariel', 16))
    s.configure("TFrame", background='white')

    content = ttk.Frame(root, padding=(3, 3, 12, 12))
    greeting_label = ttk.Label(content, text="Hi Guy, welcome to the reports master", anchor="center")

    start_button = ttk.Button(content, text="Go!", state=DISABLED, command=thread_worker, style="Go.TButton")

    bavli_label = ttk.Label(content, text="Your sheet URL")
    bavli_string_var = tk.StringVar()
    bavli_string_var.trace("w", lambda name, index, mode, sv=bavli_string_var: check_both_url())
    bavli_url = ttk.Entry(content, textvariable=bavli_string_var)
    external_string_var = tk.StringVar()
    external_string_var.trace("w", lambda name, index, mode, sv=bavli_string_var: check_both_url())
    external_label = ttk.Label(content, text="External sheet URL")
    external_url = ttk.Entry(content, textvariable=external_string_var)
    urls.extend([bavli_url, external_url])

    matches_var = BooleanVar(value=False)
    show_matches = ttk.Checkbutton(content, text="Show Matches", variable=matches_var, onvalue=True)

    frame = ttk.LabelFrame(content, text="Status", borderwidth=5, relief="ridge")
    console_ui = ConsoleUi(frame=frame)

    content.grid(column=0, row=0, sticky=(N, S, E, W))
    greeting_label.grid(column=0, row=0, columnspan=3, sticky=(N, S, E, W))

    bavli_label.grid(column=0, row=1, sticky=(N, W), padx=5)
    bavli_url.grid(column=1, row=1, columnspan=2, sticky=(N, E, W), pady=5, padx=5)
    external_label.grid(column=0, row=2, sticky=(N, W), padx=5)
    external_url.grid(column=1, row=2, columnspan=2, sticky=(N, E, W), pady=5, padx=5)

    # show_matches.grid(column=0, row=3)

    frame.grid(column=0, row=4, columnspan=3, rowspan=3, sticky=(N, S, E, W))
    start_button.grid(column=1, row=7, sticky=(N, S, E, W))

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    content.columnconfigure(1, weight=3)
    content.columnconfigure(2, weight=3)
    content.rowconfigure(4, weight=1)
    content.rowconfigure(5, weight=1)
    content.rowconfigure(6, weight=1)
    content.rowconfigure(7, weight=1)

    root.mainloop()
