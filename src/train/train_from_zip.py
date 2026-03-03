from __future__ import annotations

import random
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from ultralytics import YOLO


IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class TrainConfig:
    zip_path: str                         
    run_name: str = "cam01_yolo"          
    train_pct: float = 0.90               
    seed: int = 42
    base_model: str = "yolov8n.pt"        
    epochs: int = 60
    imgsz: int = 640
    device: str | None = None             
    project_models_dir: str = "models"    


def _unzip(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)


def _find_images_labels_root(extracted_dir: Path) -> tuple[Path, Path]:
    direct_images = extracted_dir / "images"
    direct_labels = extracted_dir / "labels"
    if direct_images.exists() and direct_labels.exists():
        return direct_images, direct_labels

    images_candidates = [p for p in extracted_dir.rglob("images") if p.is_dir()]
    labels_candidates = [p for p in extracted_dir.rglob("labels") if p.is_dir()]

    for img_dir in images_candidates:
        for lbl_dir in labels_candidates:
            if img_dir.parent == lbl_dir.parent:
                return img_dir, lbl_dir


    if images_candidates and labels_candidates:
        return images_candidates[0], labels_candidates[0]

    raise FileNotFoundError(
        f"Could not find 'images' and 'labels' folders inside: {extracted_dir}"
    )


def _list_images(images_dir: Path) -> list[Path]:
    imgs = []
    for p in images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            imgs.append(p)
    imgs.sort()
    if not imgs:
        raise FileNotFoundError(f"No images found in: {images_dir}")
    return imgs


def _make_split(
    images_dir: Path,
    labels_dir: Path,
    out_base: Path,
    train_pct: float,
    seed: int
) -> tuple[Path, Path]:

    rnd = random.Random(seed)
    imgs = _list_images(images_dir)
    rnd.shuffle(imgs)

    n_train = int(len(imgs) * train_pct)
    train_imgs = imgs[:n_train]
    val_imgs = imgs[n_train:]

    # Output dirs
    img_train_dir = out_base / "images" / "train"
    img_val_dir = out_base / "images" / "val"
    lbl_train_dir = out_base / "labels" / "train"
    lbl_val_dir = out_base / "labels" / "val"
    for d in [img_train_dir, img_val_dir, lbl_train_dir, lbl_val_dir]:
        d.mkdir(parents=True, exist_ok=True)

    def copy_pair(img_path: Path, img_dst_dir: Path, lbl_dst_dir: Path):
        shutil.copy2(img_path, img_dst_dir / img_path.name)
        lbl_src = labels_dir / f"{img_path.stem}.txt"
        lbl_dst = lbl_dst_dir / f"{img_path.stem}.txt"
        if lbl_src.exists():
            shutil.copy2(lbl_src, lbl_dst)
        else:
            lbl_dst.write_text("", encoding="utf-8")

    for p in train_imgs:
        copy_pair(p, img_train_dir, lbl_train_dir)
    for p in val_imgs:
        copy_pair(p, img_val_dir, lbl_val_dir)

    return img_train_dir, img_val_dir


def _read_classes_txt(classes_txt: Path) -> list[str]:
    if not classes_txt.exists():
        raise FileNotFoundError(
            f"classes.txt not found at {classes_txt}. "
            f"Create it (one class per line), e.g. car\\nbus\\ntruck"
        )
    classes = []
    for line in classes_txt.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s:
            classes.append(s)
    if not classes:
        raise ValueError("classes.txt is empty.")
    return classes


def _write_data_yaml(out_yaml: Path, dataset_root: Path, classes: list[str]) -> None:
    data = {
        "path": str(dataset_root.as_posix()),
        "train": "images/train",
        "val": "images/val",
        "names": {i: name for i, name in enumerate(classes)}
    }
    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    out_yaml.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")


def train_from_zip(cfg: TrainConfig) -> Path:
    zip_path = Path(cfg.zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    incoming_dir = zip_path.parent
    extracted_dir = incoming_dir / f"_extracted_{cfg.run_name}"
    processed_dir = Path("dataset") / "processed" / cfg.run_name

    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    if processed_dir.exists():
        shutil.rmtree(processed_dir)

    _unzip(zip_path, extracted_dir)

    images_dir, labels_dir = _find_images_labels_root(extracted_dir)

    _make_split(
        images_dir=images_dir,
        labels_dir=labels_dir,
        out_base=processed_dir,
        train_pct=cfg.train_pct,
        seed=cfg.seed,
    )

    classes_txt = extracted_dir / "classes.txt"
    classes = _read_classes_txt(classes_txt)

    data_yaml = processed_dir / "data.yaml"
    _write_data_yaml(data_yaml, processed_dir, classes)

    model = YOLO(cfg.base_model)

    results = model.train(
        data=str(data_yaml),
        epochs=cfg.epochs,
        imgsz=cfg.imgsz,
        project=cfg.project_models_dir,
        name=cfg.run_name,
        exist_ok=True,
        device=cfg.device
    )

    best_pt = Path(cfg.project_models_dir) / cfg.run_name / "weights" / "best.pt"
    if not best_pt.exists():
        candidates = list(Path(cfg.project_models_dir).rglob("best.pt"))
        if candidates:
            best_pt = candidates[0]

    print(f"\n✅ Dataset processed at: {processed_dir}")
    print(f"✅ data.yaml at: {data_yaml}")
    print(f"✅ Best model saved at: {best_pt}\n")

    return best_pt


if __name__ == "__main__":
    best = train_from_zip(
        TrainConfig(
            zip_path="dataset/incoming/data.zip",
            run_name="cam01_yolo",
            train_pct=0.90,
            base_model="yolov8n.pt",
            epochs=60,
            imgsz=640,
            device=None 
        )
    )