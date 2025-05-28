import cv2
import os

def extract_frames(video_path, interval_sec):
    # 获取视频文件名（不含扩展名）
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # 构建输出文件夹路径
    output_folder = os.path.join("output", f"{video_name}_{interval_sec}")
    os.makedirs(output_folder, exist_ok=True)

    # 打开视频文件
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"无法打开视频文件: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps

    print(f"视频时长: {duration_sec:.2f} 秒, 帧率: {fps:.2f} FPS, 总帧数: {total_frames}")

    frame_interval = int(fps * interval_sec)
    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            image_filename = os.path.join(output_folder, f"frame_{saved_count:04d}.jpg")
            cv2.imwrite(image_filename, frame)
            print(f"保存帧 {frame_count} 为 {image_filename}")
            saved_count += 1

        frame_count += 1

    cap.release()
    print(f"共保存了 {saved_count} 张图片至 {output_folder}")

if __name__ == "__main__":
    video_path = "2025-05-22-11-03-51.mkv"  # 替换为你的视频路径
    interval_sec = 5  # 每 N 秒抽取一帧

    extract_frames(video_path, interval_sec)
