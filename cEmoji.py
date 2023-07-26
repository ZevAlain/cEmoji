import tkinter as tk
from tkinter import messagebox

root = tk.Tk()

def show_message():
    messagebox.showinfo("提示", "test")

button = tk.Button(root, text="点击", command=show_message)
button.pack()

root.mainloop()
