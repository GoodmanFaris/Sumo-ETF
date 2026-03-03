import cv2
from pathlib import Path

def extract_frames(video_path: str, out_dir: str, every_seconds: float = 3.0):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = int(max(1, round(fps * every_seconds)))

    idx = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            fname = out / f"frame_{idx:08d}.jpg"
            cv2.imwrite(str(fname), frame)
            saved += 1
        idx += 1

    cap.release()
    print(f"Saved {saved} frames to {out}")

if __name__ == "__main__":
    pass

    #extract_frames(
    #    video_path=r"C:\Users\Korisnik\Desktop\EtfIsDigital\raw\videos\cam01.mp4",
    #    out_dir="raw/images",
    #    every_seconds=3.0
    #)

