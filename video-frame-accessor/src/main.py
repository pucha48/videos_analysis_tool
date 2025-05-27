import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

THUMBNAIL_SIZE = (120, 90)  # Width, Height
FRAMES_PER_ROW = 10
VISIBLE_ROWS = 5

def get_video_folders(directory):
    return [os.path.join(directory, d) for d in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, d))]

def get_frames(folder):
    return sorted([os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

def create_thumbnail(image_path):
    img = Image.open(image_path)
    img.thumbnail(THUMBNAIL_SIZE)
    return ImageTk.PhotoImage(img)

def display_frames_gui(directory):
    root = tk.Tk()
    root.title("Video Frame Viewer")

    main_frame = ttk.Frame(root)
    main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    video_folders = get_video_folders(directory)
    total_folders = len(video_folders)
    thumbnails = []  # Keep references to avoid garbage collection

    # Store row widgets for updating
    row_widgets = []

    def update_rows(start_folder_idx):
        # Clear previous widgets
        for widgets in row_widgets:
            for w in widgets:
                w.destroy()
        row_widgets.clear()

        for row in range(VISIBLE_ROWS):
            folder_idx = start_folder_idx + row
            if folder_idx >= total_folders:
                break
            folder = video_folders[folder_idx]
            frames = get_frames(folder)
            thumb_labels = []
            row_frame = ttk.Frame(main_frame)
            row_frame.grid(row=row*2, column=0, sticky="w")
            row_widgets.append([row_frame])

            # Initial display
            for col in range(FRAMES_PER_ROW):
                lbl = ttk.Label(row_frame)
                lbl.grid(row=0, column=col, padx=2, pady=2)
                thumb_labels.append(lbl)
                row_widgets[-1].append(lbl)

            def update_row(start_idx, frames=frames, thumb_labels=thumb_labels):
                for col in range(FRAMES_PER_ROW):
                    frame_idx = start_idx + col
                    if frame_idx < len(frames):
                        thumb = create_thumbnail(frames[frame_idx])
                        thumbnails.append(thumb)
                        thumb_labels[col].configure(image=thumb)
                        thumb_labels[col].image = thumb
                    else:
                        thumb_labels[col].configure(image='')
                        thumb_labels[col].image = None

            # Slider for this row
            slider_frame = ttk.Frame(main_frame)
            slider_frame.grid(row=row*2+1, column=0, sticky="w")
            row_widgets[-1].append(slider_frame)
            max_start = max(0, len(frames) - FRAMES_PER_ROW)
            slider = tk.Scale(
                slider_frame, from_=0, to=max_start, orient=tk.HORIZONTAL,
                length=FRAMES_PER_ROW * (THUMBNAIL_SIZE[0] + 4),
                command=lambda val, f=frames, t=thumb_labels: update_row(int(float(val)), f, t)
            )
            slider.pack(side=tk.LEFT, padx=5, pady=2)
            row_widgets[-1].append(slider)

            # Show initial frames
            update_row(0, frames, thumb_labels)

    # Vertical slider to control which 5 folders are visible
    def on_vertical_slide(val):
        start_folder_idx = int(float(val))
        update_rows(start_folder_idx)

    max_folder_start = max(0, total_folders - VISIBLE_ROWS)
    v_slider = tk.Scale(
        root, from_=0, to=max_folder_start, orient=tk.VERTICAL,
        length=VISIBLE_ROWS * (THUMBNAIL_SIZE[1] + 40),
        command=on_vertical_slide,
        label="Videos"
    )
    v_slider.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

    update_rows(0)

    root.mainloop()

if __name__ == "__main__":
    video_frames_directory = "./video-frame-accessor/data/"  # Update this path if needed
    if not os.path.exists(video_frames_directory):
        print(f"The directory {video_frames_directory} does not exist.")
    else:
        display_frames_gui(video_frames_directory)