import tkinter as tk

def changeLabelText(lbl, new_text):
    lbl.config(text=new_text)


def __init__():
    window = tk.Tk()
    window.title("Test Application 1")
    window.geometry("400x200")

    label = tk.Label(window, text="Nothing's pressed", font=("Times New Roman", 18))
    label.pack(padx=20, pady=20)

    button = tk.Label(window, text="Hello, World!", font=("Arial", 16))
    button.bind("<Button-1>", lambda e: changeLabelText(label, "Hello, I got clicked!"))
    button.pack(pady=50)

    window.mainloop()

if __name__ == "__main__":
    __init__()