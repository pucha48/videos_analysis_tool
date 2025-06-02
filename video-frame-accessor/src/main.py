import os
import re
import urllib.parse
import json
import tempfile
import shutil
import time
from flask import Flask, render_template, request, send_from_directory, abort, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_SIZE = (220, 180)
FRAMES_PER_ROW = 7
VISIBLE_ROWS = 3
DATA_PATH = os.path.abspath("video-frame-accessor/data/")
LABEL_FOLDER_PATH = os.path.abspath("video-frame-accessor/labels/")
SAMPLE_EVERY_X = 16  # User-defined sampling rate for UI display

app = Flask(__name__)

def get_video_folders(directory):
    return sorted([os.path.join(directory, d) for d in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, d))])

def get_frames(folder):
    return sorted([os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

def extract_float_from_filename(filename):
    match = re.search(r'([0-9]*\.?[0-9]+)(?=\.[^.]+$)', os.path.basename(filename))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0

def safe_load_json(filepath, retries=3, delay=0.05):
    for attempt in range(retries):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error reading {filepath}: {e}")
                return {}
            time.sleep(delay)

def load_labels(folder_name, labels_dir):
    label_path = os.path.join(labels_dir, f'{folder_name}.json')
    return safe_load_json(label_path)

def atomic_write_json(filepath, data):
    dirpath = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile('w', dir=dirpath, delete=False) as tf:
        json.dump(data, tf, indent=2)
        tempname = tf.name
    shutil.move(tempname, filepath)

@app.route('/')
def index():
    data_dir = request.args.get('data_dir', DATA_PATH)
    labels_dir = request.args.get('labels_dir', LABEL_FOLDER_PATH)
    folder_start = int(request.args.get('folder_start', 0))
    frame_starts = request.args.getlist('frame_start')
    frame_starts = [int(x) if x.isdigit() else 0 for x in frame_starts]
    
    video_folders = get_video_folders(data_dir)
    # Show all folders, remove slicing logic
    visible_folders = video_folders

    # Remove frame_starts padding logic since all folders are shown
    while len(frame_starts) < len(visible_folders):
        frame_starts.append(0)
    frame_starts = frame_starts[:len(visible_folders)]

    rows = []
    for idx, folder in enumerate(visible_folders):
        frames = get_frames(folder)
        # Sample frames for UI display only
        sampled_frames = frames[::SAMPLE_EVERY_X] if SAMPLE_EVERY_X > 1 else frames
        max_start = max(0, len(sampled_frames) - FRAMES_PER_ROW)
        start = min(frame_starts[idx], max_start)
        row_frames = []
        folder_name = os.path.basename(folder)
        labels = load_labels(folder_name, labels_dir)

        # --- Ensure all frames are present in labels with interpolated values ---
        total_frames = len(frames)
        if total_frames > 1:
            for i, frame_path in enumerate(frames):
                frame_filename = os.path.basename(frame_path)
                interp_val = i / (total_frames - 1)
                if frame_filename not in labels:
                    labels[frame_filename] = f"{interp_val:.2f}"
        elif total_frames == 1:
            frame_filename = os.path.basename(frames[0])
            if frame_filename not in labels:
                labels[frame_filename] = "0.00"

        # Save the updated labels for this folder
        labels_dir = os.path.abspath(LABEL_FOLDER_PATH)
        os.makedirs(labels_dir, exist_ok=True)
        label_path = os.path.join(labels_dir, f'{folder_name}.json')
        with open(label_path, 'w') as f:
            json.dump(labels, f, indent=2)
        # -----------------------------------------------------------------------

        for i in range(FRAMES_PER_ROW):
            frame_idx = start + i
            if frame_idx < len(sampled_frames):
                frame_path = sampled_frames[frame_idx]
                float_val = extract_float_from_filename(frame_path)
                img_url = "/frame_image?folder={}&img={}".format(
                    urllib.parse.quote(folder_name),
                    urllib.parse.quote(os.path.basename(frame_path))
                )
                row_frames.append({
                    'img_url': img_url,
                    'float_val': f"{float_val:.2f}",  # extracted from filename
                    'box_val': labels.get(os.path.basename(frame_path), ""),  # interpolated/user value
                    'filename': os.path.basename(frame_path)
                })
            else:
                row_frames.append(None)
        # Add sampled_filenames for robust frontend sync
        sampled_filenames = [os.path.basename(f) for f in sampled_frames]
        rows.append({
            'folder': folder_name,
            'frames': row_frames,
            'max_start': max_start,
            'start': start,
            'labels': labels,
            'sampled_filenames': sampled_filenames
        })

    return render_template(
        'viewer.html', 
        rows=rows, 
        folder_start=0,  # No longer used
        max_folder_start=0,  # No longer used
        data_dir=data_dir,
        labels_dir=labels_dir,
        frame_starts=frame_starts,
        FRAMES_PER_ROW=FRAMES_PER_ROW
    )

@app.route('/frame_image')
def frame_image():
    folder = request.args.get('folder')
    img = request.args.get('img')
    data_dir = os.path.abspath(DATA_PATH)
    if not folder or not img:
        abort(404)
    folder_path = os.path.join(data_dir, folder)
    image_path = os.path.join(folder_path, img)
    print("Trying to serve:", image_path)  # Debug print
    if not (os.path.exists(image_path) and os.path.isfile(image_path)):
        print("File not found:", image_path)  # Debug print
        abort(404)
    return send_from_directory(folder_path, img)

@app.route('/save_label', methods=['POST'])
def save_label():
    data = request.get_json()
    folder = data['folder']
    frame = data['frame']
    value = float(data['value'])
    value = max(0.0, min(1.0, value))  # Clamp between 0 and 1

    # Get labels_dir from query or default
    labels_dir = request.args.get('labels_dir',LABEL_FOLDER_PATH)
    os.makedirs(labels_dir, exist_ok=True)
    user_points_path = os.path.join(labels_dir, f'{folder}_user_points.json')
    labels_path = os.path.join(labels_dir, f'{folder}.json')
    data_dir = os.path.abspath(DATA_PATH)
    folder_path = os.path.join(data_dir, folder)
    frames = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

    # Load user points (anchors)
    if os.path.exists(user_points_path):
        try:
            with open(user_points_path, 'r') as f:
                user_points = json.load(f)
        except Exception:
            user_points = {}
    else:
        user_points = {}

    # Update/add the user value (only user input changes this file)
    user_points[frame] = f"{value:.2f}"
    with open(user_points_path, 'w') as f:
        json.dump(user_points, f, indent=2)

    # Build a sorted list of (index, value) for all user-provided frames (anchors)
    user_points_list = []
    for idx, fname in enumerate(frames):
        if fname in user_points:
            try:
                v = float(user_points[fname])
                v = max(0.0, min(1.0, v))
                user_points_list.append((idx, v))
            except Exception:
                pass

    # Add virtual anchors at start and end if not present
    if not any(idx == 0 for idx, _ in user_points_list):
        user_points_list.append((0, 0.0))
    if not any(idx == len(frames) - 1 for idx, _ in user_points_list):
        user_points_list.append((len(frames) - 1, 1.0))

    user_points_list = sorted(user_points_list, key=lambda t: t[0])

    # Interpolate for all frames using anchors only
    labels = {}
    n = len(frames)
    for i, fname in enumerate(frames):
        # Find left and right anchors
        left = None
        right = None
        for idx, v in user_points_list:
            if idx <= i:
                left = (idx, v)
            if idx >= i and right is None:
                right = (idx, v)
        # Interpolate
        if left and right:
            if left[0] == right[0]:
                interp = left[1]
            else:
                interp = left[1] + (right[1] - left[1]) * (i - left[0]) / (right[0] - left[0])
        elif left:
            interp = left[1]
        elif right:
            interp = right[1]
        else:
            interp = i / (n - 1) if n > 1 else 0.0
        interp = max(0.0, min(1.0, interp))
        labels[fname] = f"{interp:.2f}"

    # Save interpolated labels for all frames
    atomic_write_json(labels_path, labels)
    return jsonify(success=True)

@app.route('/get_labels')
def get_labels():
    folder = request.args.get('folder')
    labels_dir = request.args.get('labels_dir', LABEL_FOLDER_PATH)
    if not folder:
        return jsonify({})
    labels = load_labels(folder, labels_dir)
    return jsonify(labels)

@app.route('/save_labelling_guide', methods=['POST'])
def save_labelling_guide():
    data = request.get_json()
    folder = data['folder']
    data_dir = os.path.abspath(DATA_PATH)
    labels_dir = os.path.abspath(LABEL_FOLDER_PATH)
    user_points_path = os.path.join(labels_dir, f'{folder}_user_points.json')
    folder_path = os.path.join(data_dir, folder)
    guide_dir = os.path.join(labels_dir, 'guide')
    os.makedirs(guide_dir, exist_ok=True)

    # Load user points (anchors)
    if os.path.exists(user_points_path):
        with open(user_points_path, 'r') as f:
            user_points = json.load(f)
    else:
        return jsonify(success=False, error='No user points found')

    # Get sorted indices and values
    frames = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    user_indices = [(idx, fname, float(user_points[fname])) for idx, fname in enumerate(frames) if fname in user_points]
    if not user_indices:
        return jsonify(success=False, error='No user points found')

    # Load images and prepare for concatenation
    images = []
    captions = []
    for idx, fname, val in user_indices:
        img_path = os.path.join(folder_path, fname)
        img = Image.open(img_path).convert('RGB')
        images.append(img)
        captions.append(f'idx: {idx}  val: {val:.2f}')

    # Resize images to same height
    thumb_height = 180
    thumb_width = 220
    images = [img.resize((thumb_width, thumb_height)) for img in images]

    # Create a new image to paste all images horizontally
    total_width = thumb_width * len(images)
    caption_height = 40
    guide_img = Image.new('RGB', (total_width, thumb_height + caption_height), (255,255,255))
    draw = ImageDraw.Draw(guide_img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()
    for i, img in enumerate(images):
        guide_img.paste(img, (i*thumb_width, 0))
        # Draw caption below
        draw.text((i*thumb_width+5, thumb_height+5), captions[i], fill=(0,0,0), font=font)

    out_path = os.path.join(guide_dir, f'{folder}.png')
    guide_img.save(out_path)
    return jsonify(success=True, path=out_path)

if __name__ == "__main__":
    app.run(debug=True)
