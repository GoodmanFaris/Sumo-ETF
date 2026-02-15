from pathlib import Path
import orjson
from ultralytics import YOLO

def run_inference(weights_path: str, images_dir: str, out_dir: str, conf: float = 0.25):
    model = YOLO(weights_path)
    images = sorted(Path(images_dir).glob("*.jpg")) + sorted(Path(images_dir).glob("*.png"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    for img_path in images:
        results = model.predict(source=str(img_path), conf=conf, verbose=False)
        r = results[0]

        dets = []
        if r.boxes is not None:
            for b in r.boxes:
                xyxy = b.xyxy[0].tolist()
                cls = int(b.cls[0].item())
                score = float(b.conf[0].item())
                dets.append({"xyxy": xyxy, "cls": cls, "conf": score})

        payload = {
            "image": img_path.name,
            "detections": dets
        }
        (out / f"{img_path.stem}.json").write_bytes(orjson.dumps(payload))
    print(f"Saved detections to {out}")

if __name__ == "__main__":
    run_inference(
        weights_path="yolov8n.pt",
        images_dir="raw/images",
        out_dir="inference/detections",
        conf=0.25
    )
