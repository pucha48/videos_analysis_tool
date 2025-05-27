import os

def list_video_frame_folders(base_directory):
    """List all folders in the specified base directory."""
    return [f.path for f in os.scandir(base_directory) if f.is_dir()]

def list_frame_files(folder_path):
    """List all frame files in the specified folder."""
    return [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

def read_frame_file(file_path):
    """Read and return the contents of a frame file."""
    with open(file_path, 'rb') as file:
        return file.read()

def get_frame_file_paths(base_directory):
    """Get a dictionary of folder names and their corresponding frame file paths."""
    frame_files_dict = {}
    folders = list_video_frame_folders(base_directory)
    for folder in folders:
        frame_files = list_frame_files(folder)
        frame_files_dict[os.path.basename(folder)] = [os.path.join(folder, f) for f in frame_files]
    return frame_files_dict