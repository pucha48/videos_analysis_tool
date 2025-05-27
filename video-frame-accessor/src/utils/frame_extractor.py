import cv2
import os

def extract_frames(video_path, output_folder):
    """
    Extracts frames from a video file and saves them as images in the output folder.

    Args:
        video_path (str): Path to the video file.
        output_folder (str): Directory where frames will be saved.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    cap = cv2.VideoCapture(video_path)
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_filename = os.path.join(output_folder, f"frame_{frame_count:05d}.jpg")
        cv2.imwrite(frame_filename, frame)
        frame_count += 1

    cap.release()
    print(f"Extracted {frame_count} frames to {output_folder}")

# Example usage:
extract_frames("/Users/purushottambhardwaj/Downloads/#IndianArmy Special by Prachyam - You Will Never See Me Again.mp4", 
               "../data/frames")