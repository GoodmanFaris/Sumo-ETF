from pathlib import Path
import random
import shutil


def select_random_images(
    source_dir: str,
    dest_dir: str,
    n_images: int = 300,
    seed: int = 42
):
    """
    Select n random images from source_dir and copy them to dest_dir.
    """

    random.seed(seed)

    src = Path(source_dir)
    dst = Path(dest_dir)
    dst.mkdir(parents=True, exist_ok=True)

    images = list(src.glob("*.jpg")) 

    if len(images) == 0:
        raise ValueError("No images found in source directory.")

    if n_images > len(images):
        print(f"Requested {n_images}, but only {len(images)} available.")
        n_images = len(images)

    selected = random.sample(images, n_images)

    for img_path in selected:
        shutil.copy(img_path, dst / img_path.name)

    print(f"Copied {len(selected)} images to {dst}")


if __name__ == "__main__":
    select_random_images(
        source_dir="raw/images",
        dest_dir="dataset/images",
        n_images=300
    )